"""Export the trained fall model or pose model to ONNX.

ST-GCN export is offline and reproducible from the saved checkpoint.
Pose export delegates to Ultralytics and requires the `ultralytics` package.
TensorRT / RKNN conversion is target-hardware specific and is intentionally
documented in edge/README.md rather than faked here.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import torch

from ur_manifest import ALGO

sys.path.insert(0, str(ALGO))
from src.stgcn import DualStreamSTGCN

STGCN_CKPT = ALGO / "data/processed/stgcn/best.pt"
POSE_WEIGHTS = ALGO / "data/processed/weights/yolov8n-pose.pt"
OUT = ALGO / "data/processed/onnx"


def export_stgcn(checkpoint: Path, output: Path, opset: int) -> dict:
    if not checkpoint.is_file():
        raise FileNotFoundError(checkpoint)
    ckpt = torch.load(checkpoint, map_location="cpu", weights_only=True)
    args = ckpt.get("args") or {}
    hidden = tuple(args.get("hidden") or (64, 64, 128))
    dropout = float(args.get("dropout", 0.3))
    model = DualStreamSTGCN(hidden=hidden, dropout=dropout)
    model.load_state_dict(ckpt["model_state"])
    model.eval()

    output.parent.mkdir(parents=True, exist_ok=True)
    joint = torch.zeros(1, 3, 30, 17, dtype=torch.float32)
    motion = torch.zeros(1, 4, 30, 17, dtype=torch.float32)
    with torch.no_grad():
        torch.onnx.export(
            model,
            (joint, motion),
            str(output),
            input_names=["joint", "motion"],
            output_names=["logits"],
            opset_version=opset,
            do_constant_folding=True,
            dynamo=False,
        )
    return {
        "model": "stgcn",
        "checkpoint": str(checkpoint),
        "output": str(output),
        "opset": opset,
        "hidden": list(hidden),
        "dropout": dropout,
        "size_bytes": output.stat().st_size,
    }


def export_pose(weights: Path, output: Path, opset: int, imgsz: int) -> dict:
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise RuntimeError("Pose export requires ultralytics: pip install ultralytics") from exc
    if not weights.is_file():
        raise FileNotFoundError(weights)
    output.parent.mkdir(parents=True, exist_ok=True)
    model = YOLO(str(weights))
    exported = model.export(format="onnx", opset=opset, imgsz=imgsz, dynamic=False, simplify=False)
    exported_path = Path(exported)
    if exported_path.resolve() != output.resolve():
        shutil.copyfile(exported_path, output)
    return {
        "model": "yolov8n-pose",
        "weights": str(weights),
        "output": str(output),
        "opset": opset,
        "imgsz": imgsz,
        "size_bytes": output.stat().st_size,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=("stgcn", "pose"), default="stgcn")
    parser.add_argument("--checkpoint", type=Path, default=STGCN_CKPT)
    parser.add_argument("--weights", type=Path, default=POSE_WEIGHTS)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--opset", type=int, default=17)
    parser.add_argument("--imgsz", type=int, default=640, help="pose export only")
    args = parser.parse_args()

    if args.model == "stgcn":
        output = args.output or OUT / "stgcn_static.onnx"
        result = export_stgcn(args.checkpoint, output, args.opset)
    else:
        output = args.output or OUT / "yolov8n-pose.onnx"
        result = export_pose(args.weights, output, args.opset, args.imgsz)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
