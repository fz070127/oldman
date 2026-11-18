"""Shared paths, frame ordering and CSV format for UR Fall."""

import csv
import os
import re
from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile


ALGO = Path(__file__).resolve().parents[1]
LABELS = ALGO / "data" / "labels"
MANIFEST = LABELS / "ur_fall.csv"
FIELDS = ("seq_id", "label", "frame_dir", "frame_count", "fps",
          "fall_onset", "confusable_type", "note")


def indexed_frames(directory, seq_id):
    pattern = re.compile(rf"{re.escape(seq_id)}-cam0-rgb-(\d+)\.png", re.I)
    numbered = []
    for path in directory.iterdir():
        if path.suffix.lower() != ".png" or not path.is_file():
            continue
        match = pattern.fullmatch(path.name)
        if not match:
            raise ValueError(f"Unexpected frame filename: {path}")
        numbered.append((int(match[1]), path))
    numbered.sort()
    if not numbered:
        raise ValueError(f"No PNG frames in {directory}")
    for expected, (actual, path) in enumerate(numbered, start=1):
        if actual != expected:
            raise ValueError(f"Expected frame {expected}, found {actual}: {path}")
    return [path for _, path in numbered]


def read_manifest(path=MANIFEST):
    rows = {}
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if tuple(reader.fieldnames or ()) != FIELDS:
            raise ValueError(f"Invalid manifest header in {path}")
        for row in reader:
            seq_id = row["seq_id"]
            if None in row or None in row.values():
                raise ValueError(f"Malformed CSV row at {path}:{reader.line_num}")
            if not re.fullmatch(r"(fall|adl)-[0-9]{2}", seq_id) or row["label"] != seq_id[:-3]:
                raise ValueError(f"Invalid sequence ID or label at {path}:{reader.line_num}")
            if seq_id in rows:
                raise ValueError(f"Duplicate sequence ID: {seq_id}")
            rows[seq_id] = row
    return rows


@contextmanager
def staged_output(path):
    """Publish a complete file, keeping an existing output intact on failure."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=path.parent, suffix=path.suffix, delete=False) as tmp:
        staged = Path(tmp.name)
    try:
        yield staged
        os.replace(staged, path)
    finally:
        staged.unlink(missing_ok=True)


def write_csv(path, rows, fields=FIELDS):
    with staged_output(path) as staged:
        with staged.open("w", newline="", encoding="utf-8") as target:
            writer = csv.DictWriter(target, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
