"""B4 对照实验：在与 ST-GCN 完全相同的窗口、划分、增强与超参下训练骨架 LSTM。

结果写入 data/processed/lstm/，用于对比报告中的"ST-GCN vs LSTM"一栏。
"""

from __future__ import annotations

import argparse
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
from train_stgcn import evaluate_model, load_split, mirror_augment, set_seed

OUT = ALGO / "data/processed/lstm"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--epochs", type=int, default=150)
    parser.add_argument("--batch", type=int, default=32)
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--weight-decay", type=float, default=5e-4)
    parser.add_argument("--patience", type=int, default=20)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--hidden", type=int, default=64)
    parser.add_argument("--layers", type=int, default=2)
    parser.add_argument("--dropout", type=float, default=0.5)
    parser.add_argument("--pos-weight-cap", type=float, default=3.0)
    parser.add_argument("--scheduler", choices=("none", "plateau"), default="none",
                        help="optional ReduceLROnPlateau on validation loss")
    parser.add_argument("--scheduler-factor", type=float, default=0.5)
    parser.add_argument("--scheduler-patience", type=int, default=5)
    parser.add_argument("--flip-augment", action="store_true", default=True)
    args = parser.parse_args()

    set_seed(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    j_train, m_train, y_train = load_split("train")
    j_val, m_val, y_val = load_split("val")
    j_test, m_test, y_test = load_split("test")

    n_pos = float(y_train.sum())
    raw = (len(y_train) - n_pos) / max(n_pos, 1.0)
    if args.pos_weight_cap > 0:
        raw = min(raw, args.pos_weight_cap)
    else:
        raw = 1.0
    criterion = nn.BCEWithLogitsLoss(pos_weight=torch.tensor([raw], device=device))

    model = SkeletonLSTM(hidden=args.hidden, layers=args.layers,
                         dropout=args.dropout).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr,
                                 weight_decay=args.weight_decay)
    scheduler = None
    if args.scheduler == "plateau":
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            optimizer, mode="min", factor=args.scheduler_factor,
            patience=args.scheduler_patience,
        )
    OUT.mkdir(parents=True, exist_ok=True)
    history, best_val, best_auc, best_epoch, stale = [], float("inf"), -1.0, -1, 0
    started = time.perf_counter()
    aug_gen = torch.Generator(device=device).manual_seed(args.seed + 1)

    for epoch in range(1, args.epochs + 1):
        model.train()
        perm = np.random.permutation(len(y_train))
        losses = []
        for s in range(0, len(perm), args.batch):
            idx = perm[s:s + args.batch]
            j = torch.from_numpy(j_train[idx]).to(device)
            m = torch.from_numpy(m_train[idx]).to(device)
            t = torch.from_numpy(y_train[idx]).to(device)
            if args.flip_augment:
                mirror_augment(j, m, aug_gen)
            optimizer.zero_grad()
            loss = criterion(model(j, m), t)
            loss.backward()
            optimizer.step()
            losses.append(loss.item() * len(idx))
        val_loss, val_acc, val_auc, _ = evaluate_model(
            model, j_val, m_val, y_val, criterion, args.batch, device)
        history.append({"epoch": epoch, "train_loss": float(np.sum(losses) / len(perm)),
                        "val_loss": val_loss, "val_acc": val_acc, "val_auc": val_auc,
                        "lr": optimizer.param_groups[0]["lr"]})
        if scheduler is not None:
            scheduler.step(val_loss)
        improved = val_auc is not None and (
            val_auc > best_auc + 1e-4
            or (abs(val_auc - best_auc) <= 1e-4 and val_loss < best_val - 1e-5))
        if improved:
            best_auc, best_val, best_epoch, stale = val_auc, val_loss, epoch, 0
            torch.save({"model_state": model.state_dict(), "epoch": epoch,
                        "val_loss": val_loss, "val_acc": val_acc, "val_auc": val_auc,
                        "args": vars(args), "seed": args.seed}, OUT / "best.pt")
        else:
            stale += 1
        print(f"epoch {epoch:3d}  train {history[-1]['train_loss']:.4f}  "
              f"val {val_loss:.4f}  acc {val_acc:.3f}  "
              f"auc {val_auc if val_auc is None else round(val_auc, 3)}"
              f"{' *' if improved else ''}", flush=True)
        if stale >= args.patience:
            print(f"early stop at epoch {epoch} (best {best_epoch})")
            break

    ckpt = torch.load(OUT / "best.pt", map_location=device, weights_only=False)
    model.load_state_dict(ckpt["model_state"])
    test_loss, test_acc, test_auc, _ = evaluate_model(
        model, j_test, m_test, y_test, criterion, args.batch, device)

    model.eval()
    with torch.no_grad():
        j = torch.from_numpy(j_val[:64]).to(device)
        m = torch.from_numpy(m_val[:64]).to(device)
        model(j, m)
        if device.type == "cuda":
            torch.cuda.synchronize()
        t0, repeats = time.perf_counter(), 10
        for _ in range(repeats):
            model(j, m)
        if device.type == "cuda":
            torch.cuda.synchronize()
        ms_per_window = (time.perf_counter() - t0) / repeats / j.shape[0] * 1000

    result = {
        "model": "SkeletonLSTM(2x64)",
        "best_epoch": best_epoch,
        "best_val_loss": best_val,
        "best_val_acc": ckpt["val_acc"],
        "best_val_auc": ckpt["val_auc"],
        "test_loss": test_loss, "test_acc": test_acc, "test_auc": test_auc,
        "parameters": model.parameter_count(),
        "device": str(device),
        "ms_per_window": round(ms_per_window, 4),
        "train_windows": int(len(y_train)), "val_windows": int(len(y_val)),
        "test_windows": int(len(y_test)),
        "wall_sec": round(time.perf_counter() - started, 1),
        "args": vars(args),
    }
    with staged_output(OUT / "history.json") as tmp:
        tmp.write_text(json.dumps(history, indent=2), encoding="utf-8")
    with staged_output(OUT / "run_result.json") as tmp:
        tmp.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
