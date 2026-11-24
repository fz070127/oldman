"""B5+B6: rule-only vs model-only vs two fusion directions on frozen splits.

Fusion directions evaluated:
- fusion_rule_gated (route B5): the rule machine triggers P1; the dual-stream
  ST-GCN re-scores the 30-frame window ending at each P1 evidence frame, and
  only a model confirmation upgrades the event to P0.
- fusion_model_led: the ST-GCN scores sliding windows; any window at or above
  the threshold triggers a candidate P1, and a rule event whose evidence frame
  lies within CONFIRM_RADIUS frames of the candidate upgrades it to P0.

The window threshold is calibrated on validation SEQUENCES (maximize
fall detections minus ADL false alarms; ties prefer the higher threshold) and
never touches test. Hard negatives are broken down by confusable type.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np
import torch

from ur_manifest import ALGO, read_manifest, staged_output
from evaluate_detector import evaluate as evaluate_rule
from run_detector import CONFIG, KEYPOINTS, load_config, run_sequence

sys.path.insert(0, str(ALGO))
from src.stgcn import DualStreamSTGCN
from src.window_utils import make_window, load_slot0

WINDOWS = ALGO / "data/processed/windows"
STGCN = ALGO / "data/processed/stgcn"
HARD_NEG = ALGO / "data/labels/hard_negative.csv"
OUT = ALGO / "data/processed/b6-comparison.json"
MIN_PREFIX = 30  # frames needed before an evidence frame to score a window
CONFIRM_RADIUS = 45  # rule evidence must be within this many frames to confirm P0


def read_members(split):
    path = ALGO / "data/splits" / f"{split}.csv"
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def load_model(device, kind="stgcn"):
    """Load the frozen checkpoint of the requested backbone."""
    if kind == "lstm":
        from src.lstm import SkeletonLSTM
        ckpt = torch.load(ALGO / "data/processed/lstm/best.pt",
                          map_location=device, weights_only=False)
        args = ckpt.get("args", {})
        model = SkeletonLSTM(hidden=args.get("hidden", 64),
                             layers=args.get("layers", 2),
                             dropout=args.get("dropout", 0.5)).to(device)
    else:
        ckpt = torch.load(STGCN / "best.pt", map_location=device, weights_only=False)
        hidden = tuple(ckpt.get("args", {}).get("hidden") or (64, 64, 128))
        dropout = float(ckpt.get("args", {}).get("dropout") or 0.3)
        model = DualStreamSTGCN(hidden=hidden, dropout=dropout).to(device)
    model.load_state_dict(ckpt["model_state"])
    model.eval()
    return model


def window_probs(model, joint, motion, device, batch=64):
    probs = []
    with torch.no_grad():
        for s in range(0, len(joint), batch):
            j = torch.from_numpy(joint[s:s + batch]).to(device)
            m = torch.from_numpy(motion[s:s + batch]).to(device)
            logits = model(j, m)
            probs.append(torch.sigmoid(logits).reshape(-1).cpu().numpy())
    return np.concatenate(probs) if probs else np.zeros(0)


def sequence_windows(seq_id, manifest):
    kpts, conf, _ = load_slot0(KEYPOINTS / f"{seq_id}.npz")
    n = kpts.shape[0]
    rows = []
    start = 0
    while start + 30 <= n:
        built = make_window(kpts, conf, start, 30)
        if built is not None:
            joint, motion, _scale = built
            rows.append((start + 30, joint, motion))  # window end frame (1-based)
        start += 15
    return rows


def sequence_max_probs(members, manifest, model, device):
    """Per-sequence max sliding-window probability (stride 15)."""
    out = {}
    for member in members:
        seq_id = member["seq_id"]
        windows = sequence_windows(seq_id, manifest)
        if not windows:
            out[seq_id] = None
            continue
        joint = np.stack([w[1] for w in windows])
        motion = np.stack([w[2] for w in windows])
        probs = window_probs(model, joint, motion, device)
        out[seq_id] = float(probs.max()) if len(probs) else None
    return out


def calibrate_threshold(members, manifest, model, device):
    """Pick the window threshold maximizing (falls found - ADL false alarms)
    at sequence level on validation; ties prefer the higher threshold."""
    seq_max = sequence_max_probs(members, manifest, model, device)
    scored = [(m["label"], seq_max[m["seq_id"]]) for m in members]
    candidates = sorted({p for _lab, p in scored if p is not None})
    best_score, best_thr = -1, 1.0
    for thr in candidates:
        det = sum(1 for lab, p in scored if lab == "fall" and p is not None and p >= thr)
        fp = sum(1 for lab, p in scored if lab == "adl" and p is not None and p >= thr)
        if det - fp > best_score:
            best_score, best_thr = det - fp, float(thr)
    return best_thr, best_score


def evaluate_model_only(split, members, manifest, model, device, thr):
    rows = []
    seq_max = sequence_max_probs(members, manifest, model, device)
    windows_by_seq = {m["seq_id"]: sequence_windows(m["seq_id"], manifest) for m in members}
    for member in members:
        seq_id = member["seq_id"]
        row = manifest[seq_id]
        windows = windows_by_seq[seq_id]
        mx = seq_max[seq_id]
        detected = mx is not None and mx >= thr
        first_frame = None
        if detected:
            ends = np.array([w[0] for w in windows])
            joint = np.stack([w[1] for w in windows])
            motion = np.stack([w[2] for w in windows])
            probs = window_probs(model, joint, motion, device)
            first_frame = int(ends[np.where(probs >= thr)[0][0]])
        onset = int(row["fall_onset"]) if row["fall_onset"].strip() else None
        rows.append({"seq_id": seq_id, "label": member["label"], "detected": detected,
                     "first_frame": first_frame, "n_windows": len(windows),
                     "max_prob": mx, "onset": onset})
    return rows


def evaluate_rule_gated(split, members, manifest, model, device, thr, config):
    rows = []
    for member in members:
        seq_id = member["seq_id"]
        row = manifest[seq_id]
        result = run_sequence(seq_id, config, cache_dir=KEYPOINTS, manifest_row=row)
        kpts, conf, _ = load_slot0(KEYPOINTS / f"{seq_id}.npz")
        events = []
        for event in result["detections"]:
            entry = dict(event)
            entry["model_prob"] = None
            fe = event["evidence_frame"]
            if fe >= MIN_PREFIX:
                built = make_window(kpts, conf, fe - MIN_PREFIX, MIN_PREFIX)
                if built is not None:
                    joint, motion, _ = built
                    prob = float(window_probs(model, joint[None], motion[None], device)[0])
                    entry["model_prob"] = prob
                    entry["level"] = "P0" if prob >= thr else event["level"]
            events.append(entry)
        onset = int(row["fall_onset"]) if row["fall_onset"].strip() else None
        rows.append({"seq_id": seq_id, "label": member["label"], "onset": onset,
                     "events": events,
                     "detected": bool(events),
                     "p0": any(e["level"] == "P0" for e in events),
                     "first_frame": result["first_detection_frame"]})
    return rows


def evaluate_model_led(split, members, manifest, model, device, thr, config):
    rows = []
    for member in members:
        seq_id = member["seq_id"]
        row = manifest[seq_id]
        result = run_sequence(seq_id, config, cache_dir=KEYPOINTS, manifest_row=row)
        rule_frames = [e["evidence_frame"] for e in result["detections"]]
        windows = sequence_windows(seq_id, manifest)
        events = []
        if windows:
            ends = np.array([w[0] for w in windows])
            joint = np.stack([w[1] for w in windows])
            motion = np.stack([w[2] for w in windows])
            probs = window_probs(model, joint, motion, device)
            for i in np.where(probs >= thr)[0]:
                frame = int(ends[i])
                confirm = any(abs(rf - frame) <= CONFIRM_RADIUS for rf in rule_frames)
                events.append({"frame": frame, "evidence_frame": frame,
                               "level": "P0" if confirm else "P1",
                               "model_prob": float(probs[i]),
                               "rule_confirmed": confirm})
        onset = int(row["fall_onset"]) if row["fall_onset"].strip() else None
        rows.append({"seq_id": seq_id, "label": member["label"], "onset": onset,
                     "events": events,
                     "detected": bool(events),
                     "p0": any(e["level"] == "P0" for e in events),
                     "first_frame": events[0]["frame"] if events else None})
    return rows


def summarize(rows):
    falls = [r for r in rows if r["label"] == "fall"]
    adls = [r for r in rows if r["label"] == "adl"]
    delays = []
    for r in falls:
        if r.get("detected") and r.get("onset") and r.get("first_frame") is not None:
            delays.append(r["first_frame"] - r["onset"])
    return {
        "fall_sequences": len(falls),
        "fall_detected": sum(1 for r in falls if r.get("detected")),
        "fall_detection_rate": (sum(1 for r in falls if r.get("detected")) / len(falls)) if falls else None,
        "fall_p0": sum(1 for r in falls if r.get("p0")),
        "adl_sequences": len(adls),
        "adl_false_alarms": sum(1 for r in adls if r.get("detected")),
        "adl_p0": sum(1 for r in adls if r.get("p0")),
        "delay_frames": delays,
        "delay_median": float(np.median(delays)) if delays else None,
        "delay_sec": [round(d / 30, 3) for d in delays],
        "missed_falls": [r["seq_id"] for r in falls if not r.get("detected")],
        "adl_false_alarm_ids": [r["seq_id"] for r in adls if r.get("detected")],
    }


def hard_negative_breakdown(rows):
    if not HARD_NEG.exists():
        return {}
    types = {}
    with HARD_NEG.open(encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            types[row["seq_id"]] = row["confusable_type"]
    out = {}
    for r in rows:
        if r["label"] != "adl" or r["seq_id"] not in types:
            continue
        kind = types[r["seq_id"]]
        entry = out.setdefault(kind, {"total": 0, "false_alarms": 0, "p0": 0, "ids": []})
        entry["total"] += 1
        if r.get("detected"):
            entry["false_alarms"] += 1
            entry["ids"].append(r["seq_id"])
            if r.get("p0"):
                entry["p0"] += 1
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--splits", nargs="+", default=("val", "test"))
    parser.add_argument("--model", choices=("stgcn", "lstm"), default="stgcn",
                        help="backbone under evaluation; lstm writes a separate report")
    args = parser.parse_args()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    manifest = read_manifest()
    model = load_model(device, args.model)
    config = load_config(CONFIG)

    val_members = read_members("val")
    thr, score = calibrate_threshold(val_members, manifest, model, device)
    print(f"calibrated threshold (val sequences, det-fp={score}): {thr}")

    report = {"backbone": args.model, "threshold": thr,
              "threshold_val_objective": score,
              "confirm_radius_frames": CONFIRM_RADIUS, "splits": {}}
    for split in args.splits:
        members = read_members(split)

        rule = evaluate_rule(split, config, KEYPOINTS)
        rule_rows = [{"seq_id": r["seq_id"], "label": r["label"],
                      "detected": bool(r["detections"]),
                      "p0": any(e["level"] == "P0" for e in r["detections"]),
                      "first_frame": r["first_detection_frame"],
                      "onset": r["fall_onset"]} for r in rule["sequences"]]

        model_rows = evaluate_model_only(split, members, manifest, model, device, thr)
        gated_rows = evaluate_rule_gated(split, members, manifest, model, device, thr, config)
        led_rows = evaluate_model_led(split, members, manifest, model, device, thr, config)

        report["splits"][split] = {
            "rule_only": summarize(rule_rows),
            "model_only": summarize(model_rows),
            "fusion_rule_gated": summarize(gated_rows),
            "fusion_model_led": summarize(led_rows),
            "rule_runtime_ms_max": rule["metrics"]["max_sequence_runtime_ms"],
            "hard_negatives_rule": hard_negative_breakdown(rule_rows),
            "hard_negatives_model": hard_negative_breakdown(model_rows),
            "hard_negatives_fusion_rule_gated": hard_negative_breakdown(gated_rows),
            "hard_negatives_fusion_model_led": hard_negative_breakdown(led_rows),
            "model_sequences": model_rows,
            "fusion_model_led_sequences": led_rows,
        }
        s = report["splits"][split]
        print(f"[{split}] rule {s['rule_only']['fall_detection_rate']} "
              f"model {s['model_only']['fall_detection_rate']} "
              f"rule_gated {s['fusion_rule_gated']['fall_detection_rate']} "
              f"model_led {s['fusion_model_led']['fall_detection_rate']}")

    out_path = OUT if args.model == "stgcn" else OUT.with_name(
        f"b6-comparison-{args.model}.json")
    with staged_output(out_path) as tmp:
        tmp.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"saved: {out_path}")


if __name__ == "__main__":
    main()
