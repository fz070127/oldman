"""Dump per-window ST-GCN scores for C2 consensus experiments."""

from __future__ import annotations

import argparse
import json
import sys
from collections import OrderedDict
from pathlib import Path

import numpy as np
import torch

from ur_manifest import ALGO, read_manifest

sys.path.insert(0, str(ALGO))
from src.stgcn import DualStreamSTGCN

WINDOWS = ALGO / "data/processed/windows"
CKPT = ALGO / "data/processed/stgcn/best.pt"
OUT = ALGO / "data/processed/c2/sequence_scores.json"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, default=CKPT)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--batch", type=int, default=64)
    args = parser.parse_args()

    manifest = read_manifest()
    ckpt = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
    model_args = ckpt.get("args") or {}
    model = DualStreamSTGCN(
        hidden=tuple(model_args.get("hidden") or (64, 64, 128)),
        dropout=float(model_args.get("dropout", 0.3)),
    )
    model.load_state_dict(ckpt["model_state"])
    model.eval()

    sequences = []
    with torch.no_grad():
        for split in ("train", "val", "test"):
            with np.load(WINDOWS / f"{split}.npz", allow_pickle=False) as archive:
                joint = archive["joint"].astype(np.float32)
                motion = archive["motion"].astype(np.float32)
                meta = archive["meta"]
            probs = []
            for start in range(0, len(joint), args.batch):
                j = torch.from_numpy(joint[start:start + args.batch])
                m = torch.from_numpy(motion[start:start + args.batch])
                probs.append(torch.sigmoid(model(j, m)).numpy())
            probs = np.concatenate(probs)
            buckets = OrderedDict()
            for row, prob in zip(meta, probs, strict=True):
                key = str(row["seq_id"])
                bucket = buckets.setdefault(key, {
                    "seq_id": key, "label": str(row["label"]), "split": split,
                    "scores": [], "window_end_frames": [],
                })
                bucket["scores"].append(float(prob))
                bucket["window_end_frames"].append(int(row["end_frame"]))
            for key, bucket in buckets.items():
                onset = manifest[key]["fall_onset"].strip()
                bucket["onset"] = int(onset) if onset else None
                ends = bucket["window_end_frames"]
                steps = [b - a for a, b in zip(ends, ends[1:]) if b > a]
                # 训练划分曾用更密步长扩增样本；低质量窗口被丢弃会产生个别跳步，
                # 因此取众数作为该序列的实际采样步长。
                bucket["window_stride_frames"] = (
                    min(set(steps), key=steps.count) if steps else 30)
            sequences.extend(buckets.values())

    args.output.parent.mkdir(parents=True, exist_ok=True)
    strides = {split: sorted({s["window_stride_frames"] for s in sequences
                              if s["split"] == split}) for split in ("train", "val", "test")}
    payload = {
        "model": str(args.checkpoint),
        "score_type": "sigmoid_logits",
        "window_length_frames": 30,
        "window_stride_frames_by_split": strides,
        "note": "train 使用更密步长扩增训练窗口；C2 参数只在 val 上调并冻结于 test，二者步长一致。",
        "sequences": sequences,
    }
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"wrote {len(sequences)} sequences -> {args.output}")


if __name__ == "__main__":
    main()
