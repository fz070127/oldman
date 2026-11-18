"""Run fall detection for one sequence from its A2 NPZ cache."""

import argparse
import json
import re
import sys
from pathlib import Path
from zipfile import BadZipFile

import numpy as np
import yaml

from ur_manifest import ALGO

sys.path.insert(0, str(ALGO))
from src.fall_detector import FallDetector, load_config


CONFIG = ALGO / "configs/detector.yaml"
KEYPOINTS = ALGO / "data/processed/keypoints"


def run_sequence(seq_id, config, *, cache_dir=KEYPOINTS, manifest_row=None):
    if not re.fullmatch(r"(fall|adl)-[0-9]{2}", seq_id):
        raise ValueError(f"invalid sequence ID: {seq_id}")
    with np.load(cache_dir / f"{seq_id}.npz", allow_pickle=False) as archive:
        meta = archive["meta"]
        fps = int(meta["fps_assumed"])
        frames = archive["frames"]
        if str(meta["seq_id"]) != seq_id or fps <= 0 or not len(frames):
            raise ValueError(f"{seq_id}: invalid cache metadata or empty sequence")
        if not np.array_equal(frames, np.arange(1, len(frames) + 1)):
            raise ValueError(f"{seq_id}: expected contiguous 1-based frames")
        if manifest_row and (len(frames), fps) != (int(manifest_row["frame_count"]), int(manifest_row["fps"])):
            raise ValueError(f"{seq_id}: frame count or fps differs from the manifest")
        arrays = []
        for name, tail in (("boxes", (2, 4)), ("kpts", (2, 17, 2)), ("kpts_conf", (2, 17)),
                           ("scores", (2,)), ("n_people", ())):
            array = archive[name]
            if array.shape != (len(frames), *tail) or not np.isfinite(array).all():
                raise ValueError(f"{seq_id}: invalid {name} array")
            arrays.append(array)

    detector = FallDetector(config, fps)
    for frame, boxes, keypoints, point_scores, box_scores, people in zip(frames, *arrays):
        detector.feed(int(frame), boxes, keypoints, point_scores, box_scores, int(people))
    detections = detector.finish()
    first = detections[0] if detections else None
    return {"seq_id": seq_id, "detections": detections,
            "first_detection_frame": first["frame"] if first else None,
            "first_detection_ts_sec": first["ts_sec"] if first else None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seq", required=True)
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--cache-dir", type=Path, default=KEYPOINTS)
    args = parser.parse_args()
    try:
        result = run_sequence(args.seq, load_config(args.config), cache_dir=args.cache_dir)
    except (OSError, ValueError, TypeError, KeyError, BadZipFile, yaml.YAMLError) as exc:
        parser.exit(1, f"{exc}\n")
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
