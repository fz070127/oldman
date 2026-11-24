"""B6 泛化验证：按序列分组的 5 折交叉验证。

URFD 这份下载只有 cam0，没有 cam1，因此跨数据集/跨相机验证不可行。
这里采用**序列级分组交叉验证**：70 个序列按 fall/ADL 分层后轮转分到 5 折，
同一序列的窗口只会出现在同一折，保证验证折的序列对训练完全不可见。
每折在同一超参下重训 ST-GCN 与 LSTM，报告窗口级 AUC 与序列级 AUC
（每序列取滑窗最大概率）的均值 ± 标准差。

注意：本脚本复用 B3 已落盘的窗口 npz（train 为加密 stride），
折内密度差异只影响采样权重，不构成跨折泄漏。
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
from train_stgcn import auc_score, mirror_augment, set_seed

WINDOWS = ALGO / "data/processed/windows"
OUT = ALGO / "data/processed/cv-folds.json"
FOLDS = 5
STGCN_ARGS = dict(hidden=(48, 48, 96), lr=2e-4, weight_decay=5e-4,
                  dropout=0.5, pos_weight_cap=3.0)
LSTM_ARGS = dict(hidden=64, layers=2, lr=2e-4, weight_decay=5e-4,
                 dropout=0.5, pos_weight_cap=3.0)
EPOCHS, PATIENCE, BATCH = 80, 15, 32


def load_all():
    joint, motion, y, seq = [], [], [], []
    for split in ("train", "val", "test"):
        with np.load(WINDOWS / f"{split}.npz", allow_pickle=False) as archive:
            meta = archive["meta"]
            joint.append(archive["joint"].astype(np.float32))
            motion.append(archive["motion"].astype(np.float32))
            y.append(archive["y"].astype(np.float32))
            seq.append(meta["seq_id"].astype(str))
    return (np.concatenate(joint), np.concatenate(motion),
            np.concatenate(y), np.concatenate(seq))


def make_folds(y, seq, seed=42):
    """Stratify sequences by label, then rotate them into FOLDS groups."""
    rng = np.random.default_rng(seed)
    groups = {}
    for seq_id in np.unique(seq):
        label = int(y[seq == seq_id].max())
        groups.setdefault(label, []).append(seq_id)
    fold_of = {}
    for label in sorted(groups):
        ids = sorted(groups[label])
        rng.shuffle(ids)
        for index, seq_id in enumerate(ids):
            fold_of[seq_id] = index % FOLDS
    return [np.array([fold_of[s] for s in seq]) == k for k in range(FOLDS)], fold_of


def build_backbone(kind, device):
    if kind == "lstm":
        return SkeletonLSTM(hidden=LSTM_ARGS["hidden"], layers=LSTM_ARGS["layers"],
                            dropout=LSTM_ARGS["dropout"]).to(device)
    return DualStreamSTGCN(hidden=STGCN_ARGS["hidden"],
                           dropout=STGCN_ARGS["dropout"]).to(device)


def train_one(kind, j_tr, m_tr, y_tr, j_va, m_va, y_va, args_cfg, device, seed):
    set_seed(seed)
    n_pos = float(y_tr.sum())
    pos_weight = min((len(y_tr) - n_pos) / max(n_pos, 1.0), args_cfg["pos_weight_cap"])
    criterion = nn.BCEWithLogitsLoss(
        pos_weight=torch.tensor([pos_weight], device=device))
    model = build_backbone(kind, device)
    optimizer = torch.optim.Adam(model.parameters(), lr=args_cfg["lr"],
                                 weight_decay=args_cfg["weight_decay"])
    aug_gen = torch.Generator(device=device).manual_seed(seed + 1)
    best_auc, best_state, stale = -1.0, None, 0
    for epoch in range(1, EPOCHS + 1):
        model.train()
        perm = np.random.permutation(len(y_tr))
        for s in range(0, len(perm), BATCH):
            idx = perm[s:s + BATCH]
            j = torch.from_numpy(j_tr[idx]).to(device)
            m = torch.from_numpy(m_tr[idx]).to(device)
            t = torch.from_numpy(y_tr[idx]).to(device)
            mirror_augment(j, m, aug_gen)
            optimizer.zero_grad()
            criterion(model(j, m), t).backward()
            optimizer.step()
        model.eval()
        probs = predict(model, j_va, m_va, device)
        val_auc = auc_score(y_va.astype(np.int64), probs)
        if val_auc is not None and val_auc > best_auc + 1e-4:
            best_auc = val_auc
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
            stale = 0
        else:
            stale += 1
        if stale >= PATIENCE:
            break
    if best_state is not None:
        model.load_state_dict(best_state)
    return model, best_auc


def predict(model, joint, motion, device, batch=64):
    model.eval()
    out = []
    with torch.no_grad():
        for s in range(0, len(joint), batch):
            j = torch.from_numpy(joint[s:s + batch]).to(device)
            m = torch.from_numpy(motion[s:s + batch]).to(device)
            out.append(torch.sigmoid(model(j, m)).reshape(-1).cpu().numpy())
    return np.concatenate(out)


def sequence_auc(probs, y, seq, fold_mask):
    """Sequence-level AUC: one score (max window prob) per sequence."""
    seq_va, y_va = seq[fold_mask], y[fold_mask]
    ids = sorted(set(seq_va))
    scores = np.array([probs[seq_va == s].max() for s in ids])
    labels = np.array([int(y_va[seq_va == s].max()) for s in ids])
    return auc_score(labels, scores), labels, scores


def main():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    joint, motion, y, seq = load_all()
    folds, fold_of = make_folds(y, seq)
    print(f"windows={len(y)} positives={int(y.sum())} sequences={len(fold_of)}")

    summary = {"protocol": "sequence-grouped 5-fold CV (stratified by fall/adl)",
               "note": "URFD 本份数据仅 cam0，无跨相机验证；此为序列级泛化证据",
               "folds": FOLDS, "windows": int(len(y)),
               "positive_windows": int(y.sum()),
               "models": {}}
    started = time.perf_counter()

    for kind, cfg in (("stgcn", STGCN_ARGS), ("lstm", LSTM_ARGS)):
        rows = []
        for k in range(FOLDS):
            va = folds[k]
            tr = ~va
            model, val_auc = train_one(kind, joint[tr], motion[tr], y[tr],
                                       joint[va], motion[va], y[va], cfg,
                                       device, 42 + k)
            probs = predict(model, joint[va], motion[va], device)
            seq_auc, labels, _ = sequence_auc(probs, y, seq, va)
            row = {
                "fold": k,
                "train_windows": int(tr.sum()), "val_windows": int(va.sum()),
                "val_sequences": int(len(set(seq[va]))),
                "val_fall_sequences": int(labels.sum()),
                "window_auc": None if val_auc is None else round(float(val_auc), 4),
                "sequence_auc": None if seq_auc is None else round(float(seq_auc), 4),
            }
            rows.append(row)
            print(f"{kind} fold {k}: win_auc={row['window_auc']} "
                  f"seq_auc={row['sequence_auc']}", flush=True)
        win = [r["window_auc"] for r in rows if r["window_auc"] is not None]
        sq = [r["sequence_auc"] for r in rows if r["sequence_auc"] is not None]
        summary["models"][kind] = {
            "folds": rows,
            "window_auc_mean": round(float(np.mean(win)), 4),
            "window_auc_std": round(float(np.std(win)), 4),
            "sequence_auc_mean": round(float(np.mean(sq)), 4),
            "sequence_auc_std": round(float(np.std(sq)), 4),
        }
        print(f"{kind}: window_auc {summary['models'][kind]['window_auc_mean']} "
              f"± {summary['models'][kind]['window_auc_std']}, "
              f"sequence_auc {summary['models'][kind]['sequence_auc_mean']} "
              f"± {summary['models'][kind]['sequence_auc_std']}", flush=True)

    summary["wall_sec"] = round(time.perf_counter() - started, 1)
    with staged_output(OUT) as tmp:
        tmp.write_text(json.dumps(summary, ensure_ascii=False, indent=2),
                       encoding="utf-8")
    print(json.dumps({m: {k: v for k, v in summary["models"][m].items() if k != "folds"}
                      for m in summary["models"]}, ensure_ascii=False, indent=2))
    print(f"written {OUT}")


if __name__ == "__main__":
    main()
