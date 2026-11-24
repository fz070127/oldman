"""用 UR Fall Detection 数据集的真实帧标定单帧图片检测阈值。"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.image_detection import detect_bytes  # noqa: E402

MANIFEST = ROOT / "algo/data/labels/ur_fall.csv"
SAMPLES = (
    ("fall-01", (80, 100, 130)),
    ("fall-02", (50, 70, 95)),
    ("fall-03", (165, 190, 210)),
    ("adl-03", (60, 120, 170)),
    ("adl-04", (50, 100, 140)),
    ("adl-13", (80, 130, 180)),
)

rows = {}
with MANIFEST.open(encoding="utf-8-sig", newline="") as file:
    for row in csv.DictReader(file):
        rows[row["seq_id"]] = row

results = []
for seq, frames in SAMPLES:
    directory = (ROOT / "algo" / rows[seq]["frame_dir"]).resolve()
    for frame in frames:
        path = directory / f"{seq}-cam0-rgb-{frame:03d}.png"
        if not path.exists():
            print("MISSING", path)
            continue
        result = detect_bytes(path.read_bytes())
        results.append((seq, frame, rows[seq]["label"], result))
        geometry = result["geometry"] or {}
        model_score = result["modelScore"]
        score = f"{model_score:.4f}" if model_score is not None else "—"
        print(
            f"{seq:8s} f{frame:3d} {rows[seq]['label']:4s} "
            f"model={score} status={result['status']:8s} "
            f"angle={geometry.get('torsoAngle')} "
            f"aspect={geometry.get('aspectRatio')} "
            f"height={geometry.get('bodyHeight')}"
        )

print("\nSUMMARY")
for label in ("fall", "adl"):
    values = [r[3]["modelScore"] for r in results if r[2] == label and r[3]["modelScore"] is not None]
    if values:
        print(f"{label}: n={len(values)} min={min(values):.4f} max={max(values):.4f} "
              f"mean={sum(values)/len(values):.4f}")
