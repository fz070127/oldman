"""B4: 由 history.json 回读绘制训练/验证曲线（loss + val AUC）。

图只用于报告，不参与任何指标计算；数据全部来自落盘的 history.json。
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Windows 自带中文字体，避免标题出现方框
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

ALGO = Path(__file__).resolve().parents[1]
FIG = ALGO / "reports/figures"
RUNS = {
    "stgcn": ("ST-GCN（双流）", ALGO / "data/processed/stgcn/history.json"),
    "lstm": ("骨架 LSTM（对照）", ALGO / "data/processed/lstm/history.json"),
}


def plot_run(key, title, history_path):
    history = json.loads(history_path.read_text(encoding="utf-8"))
    epochs = [row["epoch"] for row in history]
    train_loss = [row["train_loss"] for row in history]
    val_loss = [row["val_loss"] for row in history]
    val_auc = [row["val_auc"] for row in history]

    fig, axes = plt.subplots(1, 2, figsize=(11, 4), dpi=160)
    axes[0].plot(epochs, train_loss, label="train loss", color="#1f77b4")
    axes[0].plot(epochs, val_loss, label="val loss", color="#d62728")
    axes[0].set_xlabel("epoch")
    axes[0].set_ylabel("BCE loss")
    axes[0].set_title(f"{title} · loss")
    axes[0].legend()
    axes[0].grid(alpha=0.3)

    scored = [(e, a) for e, a in zip(epochs, val_auc) if a is not None]
    if scored:
        xs, ys = zip(*scored)
        axes[1].plot(xs, ys, label="val AUC", color="#2ca02c")
        best = max(scored, key=lambda item: item[1])
        axes[1].scatter([best[0]], [best[1]], color="#2ca02c", zorder=3)
        axes[1].annotate(f"best {best[1]:.3f} @{best[0]}",
                         xy=best, xytext=(8, -14), textcoords="offset points",
                         fontsize=9)
        axes[1].set_ylim(0.4, 1.02)
    axes[1].set_xlabel("epoch")
    axes[1].set_ylabel("val AUC")
    axes[1].set_title(f"{title} · validation AUC")
    axes[1].legend()
    axes[1].grid(alpha=0.3)

    fig.tight_layout()
    out = FIG / f"training_curves_{key}.png"
    fig.savefig(out)
    plt.close(fig)
    return out, len(history)


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    for key, (title, path) in RUNS.items():
        if not path.exists():
            print(f"skip {key}: {path} missing")
            continue
        out, n = plot_run(key, title, path)
        print(f"{key}: {n} epochs -> {out}")


if __name__ == "__main__":
    main()
