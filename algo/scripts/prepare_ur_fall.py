"""Index the cam0 RGB frame directories without copying any images."""

import argparse
import os
import re
from pathlib import Path
from statistics import median

from ur_manifest import ALGO, MANIFEST, indexed_frames, read_manifest, write_csv


DEFAULT_ROOT = ALGO.parent / "sumanpunshi/ur-fall-detection-dataset/versions/1/UR_data"
FPS = 30


def scan(root, previous):
    rows = []
    for category in ("Fall", "ADL"):
        label = category.lower()
        folder = root / category
        sequence_dirs = sorted(p for p in folder.iterdir()
                               if p.is_dir() and re.fullmatch(rf"{label}-[0-9]{{2}}-cam0-rgb", p.name))
        if not sequence_dirs:
            raise ValueError(f"No cam0 RGB sequences found in {folder}")
        for outer in sequence_dirs:
            seq_id = outer.name.removesuffix("-cam0-rgb")
            inner = outer / outer.name
            leaf = inner if inner.is_dir() else outer
            count = len(indexed_frames(leaf, seq_id))
            try:
                frame_dir = Path(os.path.relpath(leaf, ALGO)).as_posix()
            except ValueError:  # Windows cannot express a relative path across drives.
                frame_dir = leaf.as_posix()
            old = previous.get(seq_id, {})
            rows.append(dict(seq_id=seq_id, label=label, frame_dir=frame_dir,
                             frame_count=count, fps=FPS, fall_onset=old.get("fall_onset", ""),
                             confusable_type=old.get("confusable_type", ""), note=old.get("note", "")))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args()
    try:
        previous = read_manifest() if MANIFEST.exists() else {}
        rows = scan(args.raw_root.resolve(), previous)
        write_csv(MANIFEST, rows)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"{exc}\n")
    print("class  sequences  frames  duration_seconds_per_sequence (min / median / max)")
    for label in ("fall", "adl"):
        counts = [r["frame_count"] for r in rows if r["label"] == label]
        print(f"{label:5}  {len(counts):9}  {sum(counts):6}  "
              f"{min(counts)/FPS:.2f} / {median(counts)/FPS:.2f} / {max(counts)/FPS:.2f}")
    print(MANIFEST)


if __name__ == "__main__":
    main()
