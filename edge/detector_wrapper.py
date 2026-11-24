"""Adapt live poses to the same A3 state machine used in offline evaluation."""
import logging
import sys
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from uuid import uuid4

ALGO = Path(__file__).resolve().parents[1] / "algo"
sys.path.insert(0, str(ALGO))
from src.fall_detector import FallDetector, FurnitureROI, load_config


class Pose:
    def __init__(self, weights, threads, imgsz, device="cpu"):
        import cv2
        import numpy as np
        import torch
        from ultralytics import YOLO

        if not weights.is_file():
            raise FileNotFoundError(f"Missing pose weights: {weights}")
        self.device = device
        self.model = YOLO(str(weights), task="pose")
        self.imgsz = imgsz
        cv2.setNumThreads(1)
        if device == "cpu":
            torch.set_num_threads(threads)
        self.predict(np.zeros((480, 640, 3), dtype=np.uint8))
        if device == "cpu":
            torch.set_num_threads(threads)

    def predict(self, image):
        result = self.model.predict(image, device=self.device, imgsz=self.imgsz,
                                    conf=0.25, max_det=2, verbose=False)[0]
        boxes = result.boxes
        if len(boxes) == 0:
            return (), (), (), (), 0
        return (boxes.xyxy.cpu().numpy(), result.keypoints.xy.cpu().numpy(),
                result.keypoints.conf.cpu().numpy(), boxes.conf.cpu().numpy(), len(boxes))


class StreamDetector:
    def __init__(self, settings, roi, fps, width, height, stride):
        base = load_config(Path(settings["rules"]))
        overrides = dict(frame_width=width, frame_height=height,
                         motion_window_sec=settings["motion_window_sec"])
        if roi is not None:
            overrides["furniture_rois"] = tuple(FurnitureROI(tuple(r["rect"]), r["action"]) for r in roi)
        self.stride = stride
        self.engine = FallDetector(replace(base, **overrides), fps / stride)
        self.stgcn = self._load_stgcn(settings) if stride == 1 else None
        model_settings = settings.get("stgcn") or {}
        if stride != 1 and model_settings and model_settings.get("enabled", True):
            logging.warning("ST-GCN requires every source frame; using rules with stride %d", stride)

    @staticmethod
    def _load_stgcn(settings):
        cfg = settings.get("stgcn")
        if not cfg or not cfg.get("enabled", True):
            return None
        try:
            from model_confirm import StgcnConfirm
            consensus = settings.get("consensus") or {}
            if not consensus.get("enabled", False):
                consensus = None
            return StgcnConfirm(cfg["weights"], cfg["threshold"],
                                cfg.get("device", "cpu"), consensus=consensus)
        except (FileNotFoundError, ImportError, RuntimeError) as error:
            logging.getLogger(__name__).warning("ST-GCN confirm disabled: %s", error)
            return None

    def feed(self, source_frame, pose):
        frame = (source_frame - 1) // self.stride + 1
        self.engine.feed(frame, *pose)
        if self.stgcn is not None:
            self.stgcn.feed_pose(frame, pose)
        events = self._drain()
        out = []
        for detection in events:
            if self.stgcn is not None:
                self.stgcn.rule_evidence(detection["evidence_frame"])
                if detection["level"] == "P1":
                    # upgrade path 1: the current window re-scores above the
                    # threshold; path 2: the model already fired within the
                    # confirm radius (streaming memory instead of hindsight).
                    prob = self.stgcn.confirm_rule_event()
                    recent = self.stgcn.recent_model_alert(detection["evidence_frame"])
                    if prob is not None:
                        detection = dict(detection, level="P0", confidence=prob,
                                         model_prob=prob)
                    elif recent is not None:
                        detection = dict(detection, level="P0",
                                         model_prob=recent)
            out.append(detection)
        if self.stgcn is not None:
            candidate = self.stgcn.model_event(frame, allow_alert=not events)
            if candidate is not None:
                level, prob, signals = candidate
                out.append({"level": level, "confidence": prob, "frame": frame,
                            "evidence_frame": frame, "signals": signals,
                            "track_id": 0, "model_prob": prob})
        return out

    def finish_file(self):
        self.engine.finish()
        return self._drain()

    def _drain(self):
        # A3 can emit P1 then P0 for the same fall in a single feed.
        events = {}
        for d in self.engine.detections:
            events[d["track_id"], d["evidence_frame"]] = d
        self.engine.detections.clear()
        return list(events.values())

    def source_evidence(self, detection):
        return 1 + (detection["evidence_frame"] - 1) * self.stride

    def payload(self, detection, device, elder, occurred_at):
        sig = detection["signals"]
        still = (detection["frame"] - detection["evidence_frame"]) / self.engine.fps
        features = dict(torsoAngle=sig["torso_angle"], heightDrop=sig["height_drop"],
                        stillDurationSec=round(still, 3), trackId=detection["track_id"],
                        aspectRatio=sig["aspect_ratio"], kpConf=sig["kp_conf"])
        if "model_prob" in detection:
            features["modelProb"] = detection["model_prob"]
        return make_event(device, elder, detection["level"], detection["confidence"], features, occurred_at)


def make_event(device, elder, level, confidence, features, occurred_at):
    return dict(eventId=str(uuid4()), deviceNo=device, elderId=elder, type="FALL", level=level,
                confidence=confidence, occurredAt=datetime.fromtimestamp(occurred_at).astimezone().isoformat(),
                features=features, algoVersion="fall-v1.0.0", snapshotUrl=None, clipUrl=None)
