"""B4: train the dual-stream ST-GCN on the B3 window dataset.

Fixed seed, class-weighted BCE, Adam, early stopping on validation loss.
Optional ReduceLROnPlateau scheduler is off by default to preserve published runs.
Saves the best checkpoint, per-epoch history, and a run config so results
are reproducible. No scikit-learn dependency: AUC/AP are computed by hand.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

from ur_manifest import ALGO, staged_output

sys.path.insert(0, str(ALGO))
from src.stgcn import DualStreamSTGCN

WINDOWS = ALGO / "data/processed/windows"
OUT = ALGO / "data/processed/stgcn"
SEED = 42

# COCO 17-keypoint left/right swap pairs (topology-preserving mirror augment).
FLIP_PAIRS = [(1, 2), (3, 4), (5, 6), (7, 8), (9, 10), (11, 12), (13, 14), (15, 16)]
FLIP_PERM = np.arange(17)
for a, b in FLIP_PAIRS:
    FLIP_PERM[a], FLIP_PERM[b] = b, a


def mirror_augment(joint, motion, generator):
    """Flip a random subset of samples horizontally in-place on device.

    joint (N,3,T,V): negate x (channel 0); motion (N,4,T,V): negate vx and ax
    (channels 0 and 2). The L/R joint swap keeps the skeleton graph valid.
    """
    n = joint.shape[0]
    mask = torch.rand(n, device=joint.device, generator=generator) < 0.5
    if not mask.any():
        return
    perm = torch.as_tensor(FLIP_PERM, device=joint.device, dtype=torch.long)
    idx = mask.nonzero(as_tuple=True)[0]
    joint[idx, 0] = -joint[idx, 0]
    motion[idx, 0] = -motion[idx, 0]
    motion[idx, 2] = -motion[idx, 2]
    joint[idx] = joint[idx][..., perm]
    motion[idx] = motion[idx][..., perm]


def set_seed(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def load_split(split):
    with np.load(WINDOWS / f"{split}.npz", allow_pickle=False) as archive:
        return (archive["joint"].astype(np.float32),
                archive["motion"].astype(np.float32),
                archive["y"].astype(np.float32))


def auc_score(y_true, scores):
    order = np.argsort(scores)
    ranks = np.empty_like(order, dtype=np.float64)
    ranks[order] = np.arange(1, len(scores) + 1)
    # Average ranks for ties.
    scores_sorted = scores[order]
    i = 0
    while i < len(scores_sorted):
        j = i
        while j + 1 < len(scores_sorted) and scores_sorted[j + 1] == scores_sorted[i]:
            j += 1
        if j > i:
            ranks[order[i:j + 1]] = (i + j + 2) / 2.0
        i = j + 1
    pos = y_true == 1
    neg = ~pos
    if not pos.any() or not neg.any():
        return None
    return float((ranks[pos].sum() - pos.sum() * (pos.sum() + 1) / 2) / (pos.sum() * neg.sum()))


def evaluate_model(model, joint, motion, y, criterion, batch, device):
    model.eval()
    losses, probs = [], []
    with torch.no_grad():
        for s in range(0, len(y), batch):
            j = torch.from_numpy(joint[s:s + batch]).to(device)
            m = torch.from_numpy(motion[s:s + batch]).to(device)
            t = torch.from_numpy(y[s:s + batch]).to(device)
            logits = model(j, m)
            losses.append(criterion(logits, t).item() * len(t))
            probs.append(torch.sigmoid(logits).cpu().numpy())
    probs = np.concatenate(probs)
    loss = float(np.sum(losses) / len(y))
    pred = (probs >= 0.5).astype(np.float32)
    acc = float((pred == y).mean())
    auc = auc_score(y.astype(np.int64), probs)
    return loss, acc, auc, probs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--epochs", type=int, default=120)
    parser.add_argument("--batch", type=int, default=32)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--patience", type=int, default=20)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--hidden", type=int, nargs=3, default=(64, 64, 128),
                        help="per-stream hidden channels")
    parser.add_argument("--dropout", type=float, default=0.3)
    parser.add_argument("--pos-weight-cap", type=float, default=0.0,
                        help="cap for BCE pos_weight; 0 disables weighting")
    parser.add_argument("--scheduler", choices=("none", "plateau"), default="none",
                        help="optional ReduceLROnPlateau on validation loss")
    parser.add_argument("--scheduler-factor", type=float, default=0.5)
    parser.add_argument("--scheduler-patience", type=int, default=5)
    parser.add_argument("--flip-augment", action="store_true",
                        help="horizontal mirror augmentation on training batches")
    args = parser.parse_args()

    set_seed(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    j_train, m_train, y_train = load_split("train")
    j_val, m_val, y_val = load_split("val")
    n_pos = float(y_train.sum())
    n_neg = float(len(y_train) - n_pos)
    raw = n_neg / max(n_pos, 1.0)
    if args.pos_weight_cap > 0:
        raw = min(raw, args.pos_weight_cap)
    else:
        raw = 1.0
    pos_weight = torch.tensor([raw], device=device)
    criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight)

    model = DualStreamSTGCN(hidden=tuple(args.hidden), dropout=args.dropout).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr,
                                 weight_decay=args.weight_decay)
    scheduler = None
    if args.scheduler == "plateau":
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            optimizer, mode="min", factor=args.scheduler_factor,
            patience=args.scheduler_patience,
        )
    OUT.mkdir(parents=True, exist_ok=True)
    history = []
    best_val = float("inf")
    best_auc = -1.0
    best_epoch = -1
    epochs_no_improve = 0
    started = time.perf_counter()
    aug_gen = torch.Generator(device=device).manual_seed(args.seed + 1)

    for epoch in range(1, args.epochs + 1):
        model.train()
        perm = np.random.permutation(len(y_train))
        train_losses = []
        for s in range(0, len(perm), args.batch):
            idx = perm[s:s + args.batch]
            j = torch.from_numpy(j_train[idx]).to(device)
            m = torch.from_numpy(m_train[idx]).to(device)
            t = torch.from_numpy(y_train[idx]).to(device)
            if args.flip_augment:
                mirror_augment(j, m, aug_gen)
            optimizer.zero_grad()
            logits = model(j, m)
            loss = criterion(logits, t)
            loss.backward()
            optimizer.step()
            train_losses.append(loss.item() * len(idx))
        val_loss, val_acc, val_auc, _ = evaluate_model(
            model, j_val, m_val, y_val, criterion, args.batch, device)
        train_loss = float(np.sum(train_losses) / len(perm))
        history.append({"epoch": epoch, "train_loss": train_loss,
                        "val_loss": val_loss, "val_acc": val_acc, "val_auc": val_auc,
                        "lr": optimizer.param_groups[0]["lr"]})
        if scheduler is not None:
            scheduler.step(val_loss)
        marker = ""
        improved = (val_auc is not None and val_auc > best_auc + 1e-4) or (
            val_auc is not None and abs(val_auc - best_auc) <= 1e-4 and val_loss < best_val - 1e-5)
        if improved:
            best_auc = max(best_auc, val_auc if val_auc is not None else best_auc)
            best_val = val_loss
            best_epoch = epoch
            epochs_no_improve = 0
            torch.save({"model_state": model.state_dict(), "epoch": epoch,
                        "val_loss": val_loss, "val_acc": val_acc, "val_auc": val_auc,
                        "args": vars(args), "seed": args.seed}, OUT / "best.pt")
            marker = " *"
        else:
            epochs_no_improve += 1
        print(f"epoch {epoch:3d}  train {train_loss:.4f}  val {val_loss:.4f}  "
              f"acc {val_acc:.3f}  auc {val_auc if val_auc is None else round(val_auc, 3)}{marker}",
              flush=True)
        if epochs_no_improve >= args.patience:
            print(f"early stop at epoch {epoch} (best {best_epoch})")
            break

    # Restore the best checkpoint and measure inference speed.
    ckpt = torch.load(OUT / "best.pt", map_location=device, weights_only=False)
    model.load_state_dict(ckpt["model_state"])
    model.eval()
    with torch.no_grad():
        j = torch.from_numpy(j_val[:64]).to(device)
        m = torch.from_numpy(m_val[:64]).to(device)
        model(j, m)  # warm-up
        torch.cuda.synchronize() if device.type == "cuda" else None
        t0 = time.perf_counter()
        repeats = 10
        for _ in range(repeats):
            model(j, m)
        if device.type == "cuda":
            torch.cuda.synchronize()
        per_window_ms = (time.perf_counter() - t0) / repeats / j.shape[0] * 1000

    # Standalone torchinfo-free parameter count.
    result = {
        "best_epoch": best_epoch,
        "best_val_loss": best_val,
        "best_val_acc": ckpt["val_acc"],
        "best_val_auc": ckpt["val_auc"],
        "parameters": model.parameter_count(),
        "device": str(device),
        "ms_per_window": round(per_window_ms, 4),
        "train_windows": int(len(y_train)),
        "val_windows": int(len(y_val)),
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
