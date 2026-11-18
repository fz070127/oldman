"""Evaluate the detector on one frozen A1 split (validation by default)."""

import argparse
import csv
import json
from pathlib import Path
from statistics import mean, median
from time import perf_counter
from zipfile import BadZipFile

import yaml

from annotate_onset import REVIEWS, read_reviews
from run_detector import CONFIG, KEYPOINTS, load_config, run_sequence
from ur_manifest import ALGO, read_manifest, staged_output


def evaluate(split, config, cache_dir):
    manifest = read_manifest()
    reviews = read_reviews(REVIEWS, manifest)
    split_path = ALGO / "data/splits" / f"{split}.csv"
    with split_path.open(encoding="utf-8-sig", newline="") as file:
        members = list(csv.DictReader(file))
    if not members or len({row["seq_id"] for row in members}) != len(members):
        raise ValueError(f"{split_path}: split is empty or has a duplicate sequence")

    rows = []
    for member in members:
        seq_id, label = member["seq_id"], member["label"]
        source = manifest[seq_id]
        if label != source["label"]:
            raise ValueError(f"{seq_id}: split label differs from the manifest")
        review = reviews.get(seq_id)
        onset = uncertainty = None
        if review and review["approved"] == "1":
            if source["fall_onset"] != review["frame"]:
                raise ValueError(f"{seq_id}: manifest onset differs from approved review")
            onset = int(source["fall_onset"])
            uncertainty = int(review["uncertainty_frames"]) if review["uncertainty_frames"] else None

        start = perf_counter()
        result = run_sequence(seq_id, config, cache_dir=cache_dir, manifest_row=source)
        runtime_ms = (perf_counter() - start) * 1000
        first = result["first_detection_frame"]
        delay = first - onset if first is not None and onset is not None else None
        rows.append({**result, "label": label, "fall_onset": onset,
                     "onset_uncertainty_frames": uncertainty, "delay_frames": delay,
                     "delay_sec": delay / int(source["fps"]) if delay is not None else None,
                     "runtime_ms": round(runtime_ms, 3)})

    falls = [row for row in rows if row["label"] == "fall"]
    adls = [row for row in rows if row["label"] == "adl"]
    hit_falls = [row for row in falls if row["detections"]]
    delay_samples = [row["delay_frames"] for row in hit_falls if row["delay_frames"] is not None]
    delay_sec = [row["delay_sec"] for row in hit_falls if row["delay_sec"] is not None]
    path_hits = {}
    for signal in ("keypoints", "bbox_only"):
        path_hits[signal] = {
            label: sum(any(event["signals"]["signal"] == signal for event in row["detections"])
                       for row in subset)
            for label, subset in (("fall", falls), ("adl", adls))
        }

    metrics = {
        "fall_sequences": len(falls), "fall_hits": len(hit_falls),
        "fall_detection_rate": len(hit_falls) / len(falls) if falls else None,
        "adl_sequences": len(adls), "adl_false_alarm_sequences": sum(bool(r["detections"]) for r in adls),
        "adl_p0_sequences": sum(any(e["level"] == "P0" for e in r["detections"]) for r in adls),
        "adl_p0_events": sum(e["level"] == "P0" for r in adls for e in r["detections"]),
        "path_hits": path_hits, "delay_sample_count": len(delay_samples),
        "delay_frames": {name: statistic(delay_samples) if delay_samples else None
                         for name, statistic in (("min", min), ("median", median), ("mean", mean), ("max", max))},
        "mean_delay_sec": mean(delay_sec) if delay_sec else None,
        "max_sequence_runtime_ms": max(row["runtime_ms"] for row in rows),
    }
    return {"split": split, "metrics": metrics, "sequences": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=("train", "val", "test"), default="val")
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--cache-dir", type=Path, default=KEYPOINTS)
    parser.add_argument("--output", type=Path, help="also save the full JSON report to this path")
    args = parser.parse_args()
    try:
        result = evaluate(args.split, load_config(args.config), args.cache_dir)
        output = json.dumps(result, indent=2, allow_nan=False)
        if args.output:
            with staged_output(args.output) as staged:
                staged.write_text(output + "\n", encoding="utf-8")
    except (OSError, ValueError, TypeError, KeyError, BadZipFile, yaml.YAMLError) as exc:
        parser.exit(1, f"{exc}\n")
    print(output)


if __name__ == "__main__":
    main()
