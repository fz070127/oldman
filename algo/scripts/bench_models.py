"""B6 指标补齐：参数量、单窗推理耗时（GPU/CPU）与 test 划分上的模型指标。

路线指标表要求"参数量 / 单帧推理耗时（GPU）"，本脚本对 ST-GCN 主干与
LSTM 对照在同一 test 窗口集上实测，结果写入 b6-benchmark.json。
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

from ur_manifest import ALGO, staged_output

sys.path.insert(0, str(ALGO))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from src.lstm import SkeletonLSTM
from src.stgcn import DualStreamSTGCN
from train_stgcn import auc_score, load_split

STGCN_DIR = ALGO / "data/processed/stgcn"
LSTM_DIR = ALGO / "data/processed/lstm"
OUT_JSON = ALGO / "data/processed/b6-benchmark.json"


def load_stgcn(device):
    ckpt = torch.load(STGCN_DIR / "best.pt", map_location=device, weights_only=False)
    args = ckpt["args"]
    model = DualStreamSTGCN(hidden=tuple(args["hidden"]),
                            dropout=args["dropout"]).to(device)
    model.load_state_dict(ckpt["model_state"])
    return model, ckpt


def load_lstm(device):
    ckpt = torch.load(LSTM_DIR / "best.pt", map_location=device, weights_only=False)
    args = ckpt["args"]
    model = SkeletonLSTM(hidden=args["hidden"], layers=args["layers"],
                         dropout=args["dropout"]).to(device)
    model.load_state_dict(ckpt["model_state"])
    return model, ckpt


def measure(model, joint, motion, device, batch=64, repeats=20):
    model.eval()
    j = torch.from_numpy(joint[:batch]).to(device)
    m = torch.from_numpy(motion[:batch]).to(device)
    with torch.no_grad():
        model(j, m)
        if device.type == "cuda":
            torch.cuda.synchronize()
        t0 = time.perf_counter()
        for _ in range(repeats):
            model(j, m)
        if device.type == "cuda":
            torch.cuda.synchronize()
    return round((time.perf_counter() - t0) / repeats / j.shape[0] * 1000, 4)


def test_metrics(model, joint, motion, y, device, batch=64):
    model.eval()
    probs = []
    with torch.no_grad():
        for s in range(0, len(y), batch):
            j = torch.from_numpy(joint[s:s + batch]).to(device)
            m = torch.from_numpy(motion[s:s + batch]).to(device)
            probs.append(torch.sigmoid(model(j, m)).reshape(-1).cpu().numpy())
    probs = np.concatenate(probs)
    pred = (probs >= 0.5).astype(np.int64)
    tp = int(((pred == 1) & (y == 1)).sum())
    fp = int(((pred == 1) & (y == 0)).sum())
    fn = int(((pred == 0) & (y == 1)).sum())
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-9)
    return {
        "auc": round(float(auc_score(y.astype(np.int64), probs)), 4),
        "acc": round(float((pred == y).mean()), 4),
        "precision_at_0.5": round(precision, 4),
        "recall_at_0.5": round(recall, 4),
        "f1_at_0.5": round(f1, 4),
        "n": int(len(y)),
        "n_positive": int(y.sum()),
    }


def main():
    j_test, m_test, y_test = load_split("test")
    results = {}
    for name, loader, dir_ in (("stgcn_dualstream", load_stgcn, STGCN_DIR),
                               ("lstm_skeleton", load_lstm, LSTM_DIR)):
        gpu = torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")
        model, ckpt = loader(gpu)
        entry = {
            "checkpoint": str((dir_ / "best.pt").relative_to(ALGO)),
            "best_epoch": ckpt["epoch"],
            "val_auc": round(float(ckpt["val_auc"]), 4),
            "parameters": model.parameter_count(),
            "ms_per_window_gpu": measure(model, j_test, m_test, gpu),
            "test": test_metrics(model, j_test, m_test, y_test, gpu),
        }
        cpu = torch.device("cpu")
        model.to(cpu)
        entry["ms_per_window_cpu"] = measure(
            model, j_test, m_test, cpu, batch=16, repeats=5)
        results[name] = entry
        print(json.dumps({name: entry}, ensure_ascii=False, indent=2), flush=True)

    payload = {
        "note": "单窗=30 帧；GPU 为 RTX 5060 Laptop；指标于冻结 test 152 窗（15 正）复算",
        "models": results,
        "ratio": {
            "param_ratio_stgcn_over_lstm": round(
                results["stgcn_dualstream"]["parameters"]
                / results["lstm_skeleton"]["parameters"], 3),
        },
    }
    with staged_output(OUT_JSON) as tmp:
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                       encoding="utf-8")
    print(f"written {OUT_JSON}")


if __name__ == "__main__":
    main()
