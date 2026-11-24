"""B3: build the skeleton time-window dataset from A2 keypoints.

Window length is 30 frames (~1 s at the assumed 30 fps) with stride 15.
Label policy (explicit, per the confirmed route, revised after B6 round 1):
- ADL sequences: every window is 0 (lying in bed without a fall stays 0).
- Fall sequences with an approved fall_onset: a window is 1 only when it
  covers the falling transition itself (start < onset <= end), so the
  model learns "falling", not "lying".
- Fall sequences without onset: windows ending within one window length
  after the sequence midpoint are treated as the transition zone and set
  to 1, source marked "approx_second_half".
Windows are written per split; a sequence never crosses splits.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np

from ur_manifest import ALGO, read_manifest, staged_output

sys.path.insert(0, str(ALGO))
from src.window_utils import make_window, load_slot0

KEYPOINTS = ALGO / "data/processed/keypoints"
OUT_DIR = ALGO / "data/processed/windows"
WINDOW = 30
STRIDE = 15
FIELDS = ("seq_id", "label", "split", "start_frame", "end_frame",
          "y", "label_source", "scale")


def sequence_label_policy(row):
    onset = row["fall_onset"].strip()
    if row["label"] == "adl":
        return None, "adl"
    if onset:
        return int(onset), "onset"
    return None, "pseudo_onset"


def estimate_pseudo_onset(kpts, conf):
    """Locate the fall transition for unannotated fall sequences.

    Uses the hip-center y trajectory (image coordinates, y grows downward):
    the onset is the center of the fastest 10-frame downward drop. Returns a
    1-based frame number or None when the trajectory is unusable.
    """
    n = kpts.shape[0]
    y = kpts[:, 11:13, 1].mean(axis=1)
    visible = conf[:, 11:13].min(axis=1) > 0.3
    if visible.sum() < max(20, n // 4):
        return None
    idx = np.arange(n)
    yg = np.interp(idx, idx[visible], y[visible])
    ys = np.convolve(yg, np.ones(3) / 3, mode="same")
    drop = np.full(n, -np.inf)
    for t in range(5, n - 5):
        drop[t] = ys[t + 5] - ys[t - 5]
    if not np.isfinite(drop).any():
        return None
    return int(np.argmax(drop)) + 1


def build_split(split, manifest, members, stride=STRIDE, post_margin=0):
    joint_list, motion_list, meta = [], [], []
    for member in members:
        seq_id = member["seq_id"]
        row = manifest[seq_id]
        kpts, conf, _people = load_slot0(KEYPOINTS / f"{seq_id}.npz")
        n = kpts.shape[0]
        onset, source = sequence_label_policy(row)
        if source == "pseudo_onset":
            onset = estimate_pseudo_onset(kpts, conf)
            if onset is None:
                onset, source = (n + 1) // 2, "approx_mid"
        start = 0
        while start + WINDOW <= n:
            built = make_window(kpts, conf, start, WINDOW)
            if built is not None:
                joint, motion, scale = built
                end = start + WINDOW  # 1-based inclusive frame number
                if row["label"] == "adl":
                    y = 0
                else:
                    # positive iff the window overlaps the fall transition
                    # [onset, onset + post_margin]; pure lying windows that
                    # start after the transition stay negative.
                    y = 1 if (start + 1 <= onset + post_margin and end >= onset) else 0
                joint_list.append(joint)
                motion_list.append(motion)
                meta.append((seq_id, row["label"], split, start + 1, end, y, source, scale))
            start += stride
    if not joint_list:
        raise ValueError(f"split {split}: no usable windows")
    joint = np.stack(joint_list)
    motion = np.stack(motion_list)
    return joint, motion, meta


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stride", type=int, default=STRIDE)
    parser.add_argument("--train-stride", type=int, default=None,
                        help="optional denser stride for the train split only")
    parser.add_argument("--post-margin", type=int, default=0,
                        help="frames after the fall onset still counted as the "
                             "transition (landing aftermath); 0 keeps the strict "
                             "transition-only policy")
    parser.add_argument("--output-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--split-dir", type=Path, default=ALGO / "data/splits")
    args = parser.parse_args()
    if args.stride < 1 or (args.train_stride is not None and args.train_stride < 1):
        parser.error("strides must be >= 1")
    if args.post_margin < 0:
        parser.error("post-margin must be >= 0")

    manifest = read_manifest()
    stats = {}
    for split in ("train", "val", "test"):
        stride = args.train_stride if (split == "train" and args.train_stride) else args.stride
        path = args.split_dir / f"{split}.csv"
        with path.open(encoding="utf-8-sig", newline="") as file:
            members = list(csv.DictReader(file))
        joint, motion, meta = build_split(split, manifest, members, stride, args.post_margin)
        labels = np.array([m[5] for m in meta], dtype=np.int64)
        out = args.output_dir / f"{split}.npz"
        with staged_output(out) as tmp:
            np.savez_compressed(
                tmp, joint=joint, motion=motion, y=labels,
                meta=np.array(meta, dtype=[("seq_id", "U8"), ("label", "U4"),
                                            ("split", "U5"), ("start_frame", "i4"),
                                            ("end_frame", "i4"), ("y", "i4"),
                                            ("label_source", "U20"), ("scale", "f4")]))
        by_source = {}
        for m in meta:
            key = (m[6], int(m[5]))
            by_source[key] = by_source.get(key, 0) + 1
        stats[split] = {
            "windows": int(labels.size),
            "positive": int(labels.sum()),
            "negative": int((labels == 0).sum()),
            "sequences": len({m[0] for m in meta}),
            "by_source_label": {f"{k[0]}/y={k[1]}": v for k, v in sorted(by_source.items())},
        }
    with staged_output(args.output_dir / "stats.json") as tmp:
        tmp.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
