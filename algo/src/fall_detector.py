"""Associate A2 detections and apply the two fall rules per person."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field, fields
from enum import Enum, auto
from itertools import product
from math import ceil, dist, isfinite

import yaml

from .features import Box, Features, center_motion, extract_features


@dataclass(frozen=True)
class FurnitureROI:
    rect: tuple[float, float, float, float]
    action: str

    def __post_init__(self):
        left, top, right, bottom = self.rect
        if not (0 <= left < right <= 1 and 0 <= top < bottom <= 1):
            raise ValueError("furniture rect must be an ordered normalized rectangle")
        if self.action not in ("suppress", "p1"):
            raise ValueError("furniture action must be suppress or p1")

    def contains(self, x, y):
        left, top, right, bottom = self.rect
        return left <= x <= right and top <= y <= bottom


@dataclass(frozen=True)
class DetectorConfig:
    frame_width: int
    frame_height: int
    drop_window_sec: float
    motion_window_sec: float
    point_conf_min: float
    kp_conf_min: float
    height_drop_min: float
    v_drop_min: float
    torso_angle_max: float
    aspect_ratio_min: float
    motion_max: float
    motion_coverage_min: float
    bbox_height_drop_min: float
    bbox_v_drop_factor: float
    bbox_aspect_ratio_min: float
    bbox_floor_margin: float
    recovery_angle_min: float
    recovery_aspect_max: float
    recovery_height_fraction: float
    track_gap_sec: float
    track_max_cost: float
    track_reacquire_iou_min: float
    furniture_rois: tuple[FurnitureROI, ...]

    def __post_init__(self):
        for item in fields(self):
            if item.name == "furniture_rois":
                continue
            value = getattr(self, item.name)
            if type(value) not in (int, float) or not isfinite(value) or value < 0:
                raise ValueError(f"{item.name} must be a finite nonnegative number")
        if min(self.frame_width, self.frame_height, self.drop_window_sec,
               self.motion_window_sec, self.motion_coverage_min, self.track_max_cost) <= 0:
            raise ValueError("frame dimensions, windows, coverage and track cost must be positive")
        if max(self.kp_conf_min, self.point_conf_min, self.height_drop_min,
               self.bbox_height_drop_min, self.motion_coverage_min, self.bbox_floor_margin,
               self.recovery_height_fraction, self.track_reacquire_iou_min) > 1:
            raise ValueError("confidence, height, coverage and floor fractions must be at most 1")
        if not 0 <= self.torso_angle_max <= self.recovery_angle_min <= 90:
            raise ValueError("torso and recovery angles must be ordered in [0, 90]")
        if self.bbox_v_drop_factor < 1:
            raise ValueError("bbox_v_drop_factor must be at least 1")


def load_config(path):
    with path.open(encoding="utf-8") as file:
        values = yaml.safe_load(file)
    if not isinstance(values, dict):
        raise ValueError("detector config must be a YAML mapping")
    values["furniture_rois"] = tuple(FurnitureROI(tuple(roi["rect"]), roi["action"])
                                     for roi in values.get("furniture_rois", []))
    return DetectorConfig(**values)


class State(Enum):
    STANDING = auto()
    FALLING = auto()
    LYING = auto()
    CONFIRMED = auto()
    REJECTED = auto()


@dataclass(frozen=True)
class Sample:
    frame: int
    box: Box
    features: Features


@dataclass(frozen=True)
class SuspectedFall:
    sample: Sample
    height_drop: float
    peak_height: float
    signal: str
    roi_action: str | None


@dataclass
class Track:
    samples: deque[Sample] = field(default_factory=deque)
    state: State = State.STANDING
    fall: SuspectedFall | None = None
    p1_emitted: bool = False


class FallDetector:
    """Collect frame-stamped detections from a complete sequence."""

    def __init__(self, config, fps):
        self.config = config
        self.fps = fps
        self.drop_frames = ceil(config.drop_window_sec * fps)
        self.motion_frames = ceil(config.motion_window_sec * fps)
        self.max_track_gap = ceil(config.track_gap_sec * fps) + 1
        self.history_frames = max(self.drop_frames, self.motion_frames + self.max_track_gap)
        self.tracks: dict[int, Track] = {}
        self.next_id = 0
        self.detections = []

    def _associate(self, frame, boxes):
        """Minimize joint match cost after maximizing the number of matched slots."""
        costs = []
        for box in boxes:
            candidates = {None: 0.0}
            for track_id, track in self.tracks.items():
                last = track.samples[-1]
                overlap = box.iou(last.box)
                if frame - last.frame > 1 and overlap < self.config.track_reacquire_iou_min:
                    continue
                distance = dist(box.center, last.box.center) / max(box.diagonal, last.box.diagonal)
                cost = distance + 0.35 * (1 - overlap)
                if cost <= self.config.track_max_cost:
                    candidates[track_id] = cost
            costs.append(candidates)
        best = (len(boxes) + 1, float("inf"))
        assignment = ()
        for match in product(*costs):
            ids = [track_id for track_id in match if track_id is not None]
            if len(ids) != len(set(ids)):
                continue
            rank = (len(boxes) - len(ids), sum(cost[track_id] for cost, track_id in zip(costs, match)))
            if rank < best:
                best, assignment = rank, match
        return assignment

    def feed(self, frame, boxes, keypoints, point_scores, box_scores, people):
        for track_id, track in list(self.tracks.items()):
            if frame - track.samples[-1].frame > self.max_track_gap:
                self._emit_p1(track)
                del self.tracks[track_id]

        observations = []
        for slot in range(min(people, len(boxes))):
            box = Box.from_xyxy(boxes[slot])
            if box is not None:
                observations.append((box, slot))
        matches = self._associate(frame, [box for box, _ in observations])
        for track_id, (box, slot) in zip(matches, observations):
            if track_id is None:
                track_id = self.next_id
                self.tracks[track_id] = Track()
                self.next_id += 1
            track = self.tracks[track_id]
            while track.samples and frame - track.samples[0].frame > self.history_frames:
                track.samples.popleft()
            previous = track.samples[-1] if track.samples else None
            features = extract_features(
                box, keypoints[slot], point_scores[slot], box_scores[slot],
                frame_height=self.config.frame_height, point_conf_min=self.config.point_conf_min,
                previous_box=previous.box if previous else None,
                elapsed_sec=(frame - previous.frame) / self.fps if previous else None,
                recent_boxes=[s.box for s in track.samples if frame - s.frame <= self.motion_frames],
            )
            sample = Sample(frame, box, features)
            self._advance(track, sample)
            track.samples.append(sample)

    def _advance(self, track, sample):
        if track.state in (State.LYING, State.CONFIRMED):
            self._continue_fall(track, sample)
            return

        history = [s for s in track.samples if sample.frame - s.frame <= self.drop_frames]
        if not history:
            return
        peak = max(history, key=lambda s: s.features.body_height)
        peak_height = peak.features.body_height
        height_drop = (peak_height - sample.features.body_height) / peak_height
        v_drop = max((s.features.v_drop for s in (*history, sample)
                      if s.frame > peak.frame and s.features.v_drop is not None), default=None)
        cfg = self.config
        if v_drop is None or v_drop <= cfg.v_drop_min or height_drop <= 0:
            track.state = State.STANDING
            return
        track.state = State.FALLING

        features = sample.features
        pose_available = self._has_reliable_pose(features)
        if (pose_available and height_drop > cfg.height_drop_min
                and features.torso_angle < cfg.torso_angle_max
                and features.aspect_ratio > cfg.aspect_ratio_min):
            signal = "keypoints"
        elif (not pose_available and height_drop > cfg.bbox_height_drop_min
              and v_drop > cfg.v_drop_min * cfg.bbox_v_drop_factor
              and features.aspect_ratio > cfg.bbox_aspect_ratio_min
              and sample.box.bottom >= cfg.frame_height * (1 - cfg.bbox_floor_margin)):
            signal = "bbox_only"
        else:
            return

        actions = {roi.action for roi in cfg.furniture_rois
                   if roi.contains(sample.box.center[0] / cfg.frame_width, sample.box.bottom / cfg.frame_height)}
        action = "suppress" if "suppress" in actions else "p1" if actions else None
        track.fall = SuspectedFall(sample, height_drop, peak_height, signal, action)
        track.p1_emitted = False
        track.state = State.LYING

    def _has_reliable_pose(self, features):
        return (features.torso_angle is not None and features.kp_conf is not None
                and features.kp_conf >= self.config.kp_conf_min)

    def _continue_fall(self, track, sample):
        fall = track.fall
        cfg = self.config
        features = sample.features
        elapsed_frames = sample.frame - fall.sample.frame
        recovered = (features.aspect_ratio < cfg.recovery_aspect_max
                     and features.body_height >= fall.peak_height * cfg.recovery_height_fraction
                     and (features.torso_angle is None or features.torso_angle >= cfg.recovery_angle_min))
        if recovered:
            if elapsed_frames <= self.motion_frames and not track.p1_emitted:
                track.state = State.REJECTED
            else:
                self._emit_p1(track)
                track.state = State.STANDING
            track.fall = None
            track.samples.clear()
            return
        if elapsed_frames < self.motion_frames or track.p1_emitted:
            return

        self._emit_p1(track)
        still_lying = (features.aspect_ratio > cfg.aspect_ratio_min
                       and (not self._has_reliable_pose(features) or features.torso_angle < cfg.torso_angle_max))
        if fall.signal == "keypoints" and fall.roi_action is None and still_lying:
            boxes = [s.box for s in track.samples if s.frame >= fall.sample.frame] + [sample.box]
            coverage = len(boxes) / (elapsed_frames + 1)
            motion = features.motion if elapsed_frames == self.motion_frames else center_motion(boxes)
            if coverage >= cfg.motion_coverage_min and motion is not None and motion < cfg.motion_max:
                track.state = State.CONFIRMED
                self._emit(fall, sample, "P0")

    def _emit_p1(self, track):
        if track.fall is not None and not track.p1_emitted:
            track.p1_emitted = True
            if track.fall.roi_action != "suppress":
                self._emit(track.fall, track.fall.sample, "P1")

    def _emit(self, fall, sample, level):
        features = sample.features
        evidence = fall.sample.features
        confidence = evidence.bbox_conf
        if fall.signal == "keypoints":
            confidence = (confidence + evidence.kp_conf) / 2
        signals = {
            "signal": fall.signal,
            "height_drop": fall.height_drop,
            "torso_angle": features.torso_angle,
            "aspect_ratio": features.aspect_ratio,
            "kp_conf": features.kp_conf,
        }
        self.detections.append({"frame": sample.frame, "ts_sec": round(sample.frame / self.fps, 3),
                                "level": level, "confidence": round(confidence, 4), "signals": signals})

    def finish(self):
        for track in self.tracks.values():
            self._emit_p1(track)
        return sorted(self.detections, key=lambda event: event["frame"])
