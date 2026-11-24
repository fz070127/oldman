"""C2 时序聚合实验：在冻结关键点上以更密步长重建滑窗并导出 ST-GCN 分数。

不改动 data/processed/windows/ 下的 B 阶段冻结产物，也不重新训练模型；
仅把同一权重在同一批关键点上以 stride=3 重新打分，用于比较多窗共识的
时间分辨率影响。输出单独文件，供 tune_consensus.py --scores 使用。
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

if str(ALGO) not in sys.path:
    sys.path.insert(0, str(ALGO))
from src.stgcn import DualStreamSTGCN
from src.window_utils import load_slot0, make_window

KEYPOINTS = ALGO / "data/processed/keypoints"
CKPT = ALGO / "data/processed/stgcn/best.pt"
OUT = ALGO / "data/processed/c2/sequence_scores_dense.json"
WINDOW = 30


def members(split):
    with (ALGO / "data/splits" / f"{split}.csv").open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stride", type=int, default=3)
    parser.add_argument("--checkpoint", type=Path, default=CKPT)
    parser.add_argument("--keypoints", type=Path, default=KEYPOINTS,
                        help="关键点目录；C1 横评时指向候选模型的输出目录")
    parser.add_argument("--splits", nargs="+", default=("val", "test"))
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--batch", type=int, default=128)
    args = parser.parse_args()
    if args.stride < 1:
        parser.error("stride 必须为正整数")
    if not args.keypoints.is_dir():
        parser.error(f"关键点目录不存在: {args.keypoints}")

    ckpt = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
    model_args = ckpt.get("args") or {}
    model = DualStreamSTGCN(
        hidden=tuple(model_args.get("hidden") or (64, 64, 128)),
        dropout=float(model_args.get("dropout", 0.3)),
    )
    model.load_state_dict(ckpt["model_state"])
    model.eval()
    manifest = read_manifest()
    sequences = []
    with torch.no_grad():
        for split in args.splits:
            for member in members(split):
                seq_id = member["seq_id"]
                kpts, conf, _ = load_slot0(args.keypoints / f"{seq_id}.npz")
                joint_list, motion_list, ends = [], [], []
                n = kpts.shape[0]
                for start in range(0, n - WINDOW + 1, args.stride):
                    built = make_window(kpts, conf, start, WINDOW)
                    if built is None:
                        continue
                    joint, motion, _scale = built
                    joint_list.append(joint)
                    motion_list.append(motion)
                    ends.append(start + WINDOW)
                if not joint_list:
                    raise ValueError(f"{seq_id}: 无可用稠密窗口")
                joint = np.stack(joint_list).astype(np.float32)
                motion = np.stack(motion_list).astype(np.float32)
                probs = []
                for s in range(0, len(joint), args.batch):
                    j = torch.from_numpy(joint[s:s + args.batch])
                    m = torch.from_numpy(motion[s:s + args.batch])
                    probs.append(torch.sigmoid(model(j, m)).reshape(-1).numpy())
                onset = manifest[seq_id]["fall_onset"].strip()
                sequences.append({
                    "seq_id": seq_id, "label": member["label"], "split": split,
                    "scores": [float(p) for p in np.concatenate(probs)],
                    "window_end_frames": ends,
                    "window_stride_frames": args.stride,
                    "onset": int(onset) if onset else None,
                })
    payload = {
        "model": str(args.checkpoint),
        "keypoints_dir": str(args.keypoints),
        "score_type": "sigmoid_logits",
        "window_length_frames": WINDOW,
        "window_stride_frames_by_split": {sp: [args.stride] for sp in args.splits},
        "note": "同一冻结 ST-GCN 权重，仅改变滑窗步长或关键点来源；不覆盖 B 阶段冻结窗口。",
        "sequences": sequences,
    }
    with staged_output(args.output) as tmp:
        tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "sequences": len(sequences),
        "windows": sum(len(s["scores"]) for s in sequences),
        "stride": args.stride,
        "output": str(args.output),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
