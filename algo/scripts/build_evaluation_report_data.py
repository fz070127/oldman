"""Compile A4 from frozen A3 results, RGB review labels and the A2 geometry."""
import hashlib
import json
from collections import defaultdict
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from statistics import mean, median

import numpy as np
import yaml

from evaluate_detector import evaluate
from run_detector import CONFIG, KEYPOINTS, FallDetector, load_config, run_sequence
from src.features import center_motion
from ur_manifest import ALGO, read_manifest, staged_output

OUT = KEYPOINTS.parent
CFG = load_config(CONFIG)


class GeometryTrace(FallDetector):
    """Reuse the A3 associations. Record observations without running its alarm state machine."""
    def __init__(self, fps):
        super().__init__(CFG, fps)
        self.observations = defaultdict(list)

    def _advance(self, track, sample):
        track_id = next(i for i, value in self.tracks.items() if value is track)
        self.observations[track_id].append(sample)


def geometry(seq, fps):
    trace = GeometryTrace(fps)
    with np.load(KEYPOINTS / f"{seq}.npz", allow_pickle=False) as a:
        for frame, *inputs in zip(*(a[key] for key in
                ("frames", "boxes", "kpts", "kpts_conf", "scores", "n_people"))):
            trace.feed(int(frame), *inputs)
    return trace.observations


def gate_counts(tracks, fps):
    # Counts are unique video frames, even when A2 has two boxes.
    gates = defaultdict(set)
    maximum = 0
    for samples in tracks.values():
        for j, sample in enumerate(samples):
            f = sample.features
            reliable = f.torso_angle is not None and f.kp_conf >= CFG.kp_conf_min
            frame = sample.frame
            gates["box"].add(frame)
            if reliable:
                gates["pose"].add(frame)
            past = [s for s in samples[max(0, j-fps):j] if frame-s.frame <= fps]
            if not past:
                continue
            peak = max(past, key=lambda s: s.features.body_height)
            drop = 1 - f.body_height / peak.features.body_height
            maximum = max(maximum, drop)
            speed = max(s.features.v_drop for s in [*past, sample] if s.frame > peak.frame)
            if drop > CFG.height_drop_min and speed > CFG.v_drop_min:
                gates["T1"].add(frame)
                if reliable and f.torso_angle < CFG.torso_angle_max:
                    gates["T1_angle"].add(frame)
                    if f.aspect_ratio > CFG.aspect_ratio_min:
                        gates["main_all"].add(frame)
            if not reliable and drop > CFG.bbox_height_drop_min and speed > CFG.v_drop_min * CFG.bbox_v_drop_factor:
                gates["B1_no_pose"].add(frame)
                if f.aspect_ratio > CFG.bbox_aspect_ratio_min:
                    gates["B1_wide"].add(frame)
                    if sample.box.bottom >= CFG.frame_height*(1-CFG.bbox_floor_margin):
                        gates["bbox_all"].add(frame)
    return {**{k:len(gates[k]) for k in ("box","pose","T1","T1_angle","main_all","B1_no_pose","B1_wide","bbox_all")},
            "last_box":max(gates["box"], default=None), "max_height_drop":maximum}


def extension(tracks, event, n, fps):
    # One scenario: repeat the actual last frame for three seconds, including any missing box.
    frame = event["frame"]
    signal = event["signals"]
    candidates = [(samples, j) for samples in tracks.values() for j,s in enumerate(samples)
                  if s.frame == frame and abs(s.features.aspect_ratio-signal["aspect_ratio"]) < 1e-7]
    if len(candidates) != 1:
        raise ValueError("ambiguous frozen trigger frame")
    samples, j = candidates[0]
    tail = samples[j:]
    last = tail[-1]
    deadline = frame + round(CFG.motion_window_sec*fps)
    if deadline <= n:
        raise ValueError("observed confirmation window needs a direct assessment")
    visible = last.frame == n
    coverage = (len(tail) + (deadline-n if visible else 0)) / (deadline-frame+1)
    motion = center_motion([s.box for s in tail]+[last.box])  # Repeated box has zero incremental motion.
    pose = last.features
    lying = pose.aspect_ratio > CFG.aspect_ratio_min and (pose.torso_angle is None or
            pose.kp_conf < CFG.kp_conf_min or pose.torso_angle < CFG.torso_angle_max)
    return dict(last_track_frame=last.frame, observed_boxes=len(tail), motion=motion, final_visible=visible,
                projected_coverage=coverage, final_lying_shape=lying,
                upgrade=bool(signal["signal"]=="keypoints" and visible and lying and
                             coverage >= CFG.motion_coverage_min and motion < CFG.motion_max))


def build():
    paths = {s: OUT/name for s,name in (("val","a3-validation.json"),("test","a3-test-final.json"))}
    inputs = {s:json.loads(p.read_text(encoding="utf-8")) for s,p in paths.items()}
    inputs["train"] = evaluate("train", CFG, KEYPOINTS)
    manifest = read_manifest()
    actions = yaml.safe_load((ALGO/"configs/confusable.yaml").read_text(encoding="utf-8"))
    rows = []
    for split in ("train","val","test"):
        for original in inputs[split]["sequences"]:
            seq = original["seq_id"]
            n, fps = (int(manifest[seq][k]) for k in ("frame_count","fps"))
            r = dict(original, split=split, frames=n, fps=fps)
            events = r["detections"]
            if r["label"]=="adl":
                r.update(action=actions[seq], review="human_video_confirmed" if seq in ("adl-36","adl-37") else "visual_frame_review")
            else:
                tracks = geometry(seq, fps)
                r["gates"] = gate_counts(tracks, fps)
                r["remaining_frames"] = n-events[0]["frame"] if events else None
                r["extension"] = extension(tracks, events[0], n, fps) if events else None
                if split in ("val","test"):
                    if r["gates"]["bbox_all"]:
                        # Paired fall-only ablation. The production config and result files are read-only inputs.
                        variant = run_sequence(seq, replace(CFG,bbox_height_drop_min=1))
                        r["no_bbox_first_frame"] = variant["first_detection_frame"]
                        r["ablation_method"] = "isolated_bbox_disabled"
                    else:
                        r["no_bbox_first_frame"] = r["first_detection_frame"]
                        r["ablation_method"] = "identical_by_absence_of_any_bbox_trigger"
            rows.append(r)
    assert len(rows)==len(set(r["seq_id"] for r in rows))==70
    assert set(actions)=={r["seq_id"] for r in rows if r["label"]=="adl"}
    summary = {}
    actions_table = {}
    for split in ("train","val","test","all"):
        subset = [r for r in rows if split=="all" or r["split"]==split]
        falls = [r for r in subset if r["label"]=="fall"]
        hits = [r for r in falls if r["detections"]]
        adls = [r for r in subset if r["label"]=="adl"]
        remainder = [r["remaining_frames"] for r in hits]
        summary[split] = dict(sequences=len(subset),frames=sum(r["frames"] for r in subset), fall=len(falls),adl=len(adls),
            any_fall=len(hits), p0_fall=sum(any(e["level"]=="P0" for e in r["detections"]) for r in falls),
            false_adl=sum(bool(r["detections"]) for r in adls), p0_adl=sum(any(e["level"]=="P0" for e in r["detections"]) for r in adls),
            remaining_min=min(remainder),remaining_max=max(remainder),full_windows=sum(n>=90 for n in remainder),
            observed_static_3s=sum(n>=90 for n in remainder), extension_upgrades=sum(r["extension"]["upgrade"] for r in hits),
            main_hits=sum(r["detections"][0]["signals"]["signal"]=="keypoints" for r in hits))
        if split in ("val","test"):
            summary[split]["no_bbox_hits"]=sum(r["no_bbox_first_frame"] is not None for r in falls)
        actions_table[split]={}
        for action in ("squat","bend","sit","lie","walk"):
            group=[r for r in adls if r["action"]==action]
            fp=sum(bool(r["detections"]) for r in group)
            actions_table[split][action]=dict(n=len(group),fp=fp,rate=fp/len(group) if group else None)
    delays={}
    for path in ("keypoints","bbox_only"):
        values=[r["delay_frames"] for r in rows if r["delay_frames"] is not None and r["detections"][0]["signals"]["signal"]==path]
        delays[path]=dict(n=len(values),frames=sorted(values),mean=mean(values) if values else None,
                          median=median(values) if values else None,mean_sec=mean(values)/30 if values else None)
    stamp=datetime.fromtimestamp(paths["test"].stat().st_mtime,timezone(timedelta(hours=8)))
    return dict(summary=summary, sequences=rows, actions=actions_table, latency=delays,
                frozen_metrics={s:inputs[s]["metrics"] for s in paths},
                baseline_test_runs=1, test_file_modified=stamp.isoformat(),
                test_sequence_runtime_sum_ms=sum(r["runtime_ms"] for r in inputs["test"]["sequences"]),
                source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [*paths.values(),CONFIG]},
                config=yaml.safe_load(CONFIG.read_text()), extraction=json.loads((OUT/"extraction_time.json").read_text()),
                extension_assumption="Repeat the final observed frame for 90 frames, including missing observations. Assess existing P1 episodes only.",
                edge_planning=dict(target_fps=15,period_ms=1000/15,rule_budget_ms=2,acquisition_pose_budget_ms=60))


def add_report_details(result):
    rows = result["sequences"]
    result["review_notes"] = {
        "adl-36": "用户已看片确认：坐到床沿，再侧躺到床面。",
        "adl-37": "用户已看片确认：坐到床沿，再侧躺到床面。",
        "adl-10": "RGB 目检：坐到软垫上，抬腿横卧。",
        "adl-11": "RGB 目检：先坐在软垫边缘，再收腿侧躺。",
    }
    causes = {
        "fall-04": "由椅旁的低姿态前扑，向画面下缘滚出；框高降幅与下降速率未同时过线。",
        "fall-08": "坐姿起跌，手先撑地；坐姿到卧地的相对框高变化不足。",
        "fall-21": "正对镜头前扑并越出画面下缘，最后阶段整个人体框丢失。",
        "fall-24": "椅边前倾、手膝撑地，身体在下缘被裁切；有足够降幅时框高下降速率偏低。",
    }
    for r in rows:
        if r["seq_id"] not in causes:
            continue
        r["failure_reason"] = causes[r["seq_id"]]
        tracks = geometry(r["seq_id"], r["fps"])
        speeds = []
        for samples in tracks.values():
            for j, sample in enumerate(samples):
                window = [s for s in samples[max(0,j-r["fps"]):j] if sample.frame-s.frame <= r["fps"]]
                if window:
                    peak = max(window,key=lambda s:s.features.body_height)
                    if 1-sample.features.body_height/peak.features.body_height > CFG.height_drop_min:
                        speeds.append(max(s.features.v_drop for s in [*window,sample] if s.frame>peak.frame))
        r["gates"]["max_speed_at_qualifying_drop"] = max(speeds,default=None)
    for split, stats in result["summary"].items():
        stats["any_rate"] = stats["any_fall"] / stats["fall"]
        stats["p0_rate"] = stats["p0_fall"] / stats["fall"]
        if "no_bbox_hits" in stats:
            stats["no_bbox_rate"] = stats["no_bbox_hits"] / stats["fall"]
            stats["net_gain_pp"] = (stats["any_fall"]-stats["no_bbox_hits"])*100/stats["fall"]
    approved = [r for r in rows if r["fall_onset"] is not None]
    result["approved_onset_count"] = len(approved)
    result["approved_detected_count"] = sum(r["delay_frames"] is not None for r in approved)
    result["confirmation_window_frames"] = round(CFG.motion_window_sec*30)
    result["test_ablation_sequences"] = [r["seq_id"] for r in rows if r["split"]=="test"
                                         and r.get("ablation_method")=="isolated_bbox_disabled"]
    return result


if __name__ == "__main__":
    with staged_output(OUT/"evaluation_results.json") as temp:
        temp.write_text(json.dumps(add_report_details(build()),ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
