"""B 阶段图集：数据划分分布 + val/test 模型评估 + 任务级对比。

所有数据均来自落盘产物（windows npz / 模型 checkpoint / b6-comparison*.json），
不重算任何标签，只做可视化。
输出目录：algo/reports/figures/
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch

from ur_manifest import ALGO

sys.path.insert(0, str(ALGO))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from bench_models import load_lstm, load_stgcn
from train_stgcn import auc_score, load_split

FIG = ALGO / "reports/figures"
PROC = ALGO / "data/processed"
WINDOWS = PROC / "windows"

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
COLORS = {"stgcn": "#1f77b4", "lstm": "#d62728"}
NAMES = {"stgcn": "ST-GCN", "lstm": "LSTM"}


def predict(model, joint, motion, device, batch=64):
    model.eval()
    out = []
    with torch.no_grad():
        for s in range(0, len(joint), batch):
            j = torch.from_numpy(joint[s:s + batch]).to(device)
            m = torch.from_numpy(motion[s:s + batch]).to(device)
            out.append(torch.sigmoid(model(j, m)).reshape(-1).cpu().numpy())
    return np.concatenate(out)


def roc_curve(y, scores):
    order = np.argsort(-scores)
    y = y[order]
    positives = max(int(y.sum()), 1)
    negatives = max(int(len(y) - y.sum()), 1)
    tpr = np.concatenate([[0.0], np.cumsum(y) / positives])
    fpr = np.concatenate([[0.0], np.cumsum(1 - y) / negatives])
    return fpr, tpr


def pr_curve(y, scores):
    order = np.argsort(-scores)
    y = y[order]
    tp = np.cumsum(y)
    precision = tp / np.arange(1, len(y) + 1)
    recall = tp / max(int(y.sum()), 1)
    return np.concatenate([[0.0], recall]), np.concatenate([[1.0], precision])


def figure_split_overview():
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), dpi=160)
    splits = ("train", "val", "test")
    totals, positives, sequences = [], [], []
    for split in splits:
        with np.load(WINDOWS / f"{split}.npz", allow_pickle=False) as archive:
            y = archive["y"]
            meta = archive["meta"]
        totals.append(int(y.size))
        positives.append(int(y.sum()))
        sequences.append(int(len(set(meta["seq_id"]))))
    x = np.arange(len(splits))
    axes[0].bar(x - 0.18, totals, width=0.34, label="窗口总数", color="#7f7f7f")
    axes[0].bar(x + 0.18, positives, width=0.34, label="正样本（跌倒过渡）", color="#d62728")
    for i, (total, pos) in enumerate(zip(totals, positives)):
        axes[0].text(i - 0.18, total + 20, str(total), ha="center", fontsize=9)
        axes[0].text(i + 0.18, pos + 20, str(pos), ha="center", fontsize=9,
                     color="#d62728")
    axes[0].set_xticks(x, [f"{s}\n({n} 序列)" for s, n in zip(splits, sequences)])
    axes[0].set_ylabel("窗口数")
    axes[0].set_title("三个划分的窗口与正样本数量")
    axes[0].legend()
    axes[0].grid(axis="y", alpha=0.3)

    ratios = [p / t * 100 for p, t in zip(positives, totals)]
    axes[1].bar(x, ratios, width=0.5, color="#ff7f0e")
    for i, ratio in enumerate(ratios):
        axes[1].text(i, ratio + 0.05, f"{ratio:.1f}%", ha="center", fontsize=9)
    axes[1].set_xticks(x, splits)
    axes[1].set_ylabel("正样本占比 (%)")
    axes[1].set_title("正负样本比例（类别不平衡程度）")
    axes[1].grid(axis="y", alpha=0.3)
    fig.tight_layout()
    out = FIG / "dataset_splits.png"
    fig.savefig(out)
    plt.close(fig)
    return out


def figure_val_test_curves(models, data):
    fig, axes = plt.subplots(2, 2, figsize=(11, 8), dpi=160)
    for row, split in enumerate(("val", "test")):
        joint, motion, y = data[split]
        for key, model in models.items():
            probs = predict(model, joint, motion, next(model.parameters()).device)
            fpr, tpr = roc_curve(y, probs)
            recall, precision = pr_curve(y, probs)
            auc = auc_score(y.astype(np.int64), probs)
            axes[row, 0].plot(fpr, tpr, color=COLORS[key],
                              label=f"{NAMES[key]} AUC={auc:.3f}")
            axes[row, 1].plot(recall, precision, color=COLORS[key],
                              label=NAMES[key])
        axes[row, 0].plot([0, 1], [0, 1], "--", color="#999", linewidth=1)
        axes[row, 0].set_xlabel("假阳性率 FPR")
        axes[row, 0].set_ylabel("真阳性率 TPR")
        axes[row, 0].set_title(f"{split} · ROC（窗口级）")
        axes[row, 0].legend(loc="lower right")
        axes[row, 0].grid(alpha=0.3)
        axes[row, 1].set_xlabel("召回率 Recall")
        axes[row, 1].set_ylabel("精确率 Precision")
        axes[row, 1].set_title(f"{split} · PR 曲线（窗口级）")
        axes[row, 1].legend(loc="upper right")
        axes[row, 1].grid(alpha=0.3)
    fig.tight_layout()
    out = FIG / "val_test_curves.png"
    fig.savefig(out)
    plt.close(fig)
    return out


def figure_confusion(models, data, thresholds):
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), dpi=160)
    split = "test"
    joint, motion, y = data[split]
    for ax, (key, model) in zip(axes, models.items()):
        probs = predict(model, joint, motion, next(model.parameters()).device)
        pred = (probs >= thresholds[key]).astype(int)
        cm = np.array([[int(((pred == 0) & (y == 0)).sum()),
                        int(((pred == 1) & (y == 0)).sum())],
                       [int(((pred == 0) & (y == 1)).sum()),
                        int(((pred == 1) & (y == 1)).sum())]])
        ax.imshow(cm, cmap="Blues")
        for r in range(2):
            for c in range(2):
                ax.text(c, r, str(cm[r, c]), ha="center", va="center",
                        fontsize=16, color="white" if cm[r, c] > cm.max() / 2 else "black")
        ax.set_xticks([0, 1], ["预测为背景", "预测为跌倒"])
        ax.set_yticks([0, 1], ["真实为 ADL", "真实为跌倒"])
        ax.set_title(f"{NAMES[key]} · test 混淆矩阵（阈值 {thresholds[key]:.4g}）")
    fig.tight_layout()
    out = FIG / "test_confusion.png"
    fig.savefig(out)
    plt.close(fig)
    return out


def figure_sequence_scores(models, data, thresholds):
    joint, motion, y = data["test"]
    with np.load(WINDOWS / "test.npz", allow_pickle=False) as archive:
        meta = archive["meta"]
    seq_ids = sorted(set(meta["seq_id"]))
    labels = {sid: int(meta["y"][meta["seq_id"] == sid].max()) for sid in seq_ids}

    fig, ax = plt.subplots(figsize=(12, 4.2), dpi=160)
    width = 0.38
    x = np.arange(len(seq_ids))
    for offset, (key, model) in zip((-width / 2, width / 2), models.items()):
        probs = predict(model, joint, motion, next(model.parameters()).device)
        scores = [probs[meta["seq_id"] == sid].max() for sid in seq_ids]
        colors = ["#d62728" if labels[sid] == 1 else "#1f77b4" for sid in seq_ids]
        ax.bar(x + offset, scores, width=width, color=colors,
               alpha=0.9 if key == "stgcn" else 0.55, label=NAMES[key])
        ax.axhline(thresholds[key], color=COLORS[key], linestyle="--", linewidth=1.2,
                   label=f"{NAMES[key]} 阈值 {thresholds[key]:.4g}")
    ax.set_xticks(x, seq_ids, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("序列最大窗口概率")
    ax.set_title("test 逐序列得分（红=真实跌倒，蓝=ADL；左右两组分别为 ST-GCN / LSTM）")
    ax.legend(fontsize=8)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    out = FIG / "test_sequence_scores.png"
    fig.savefig(out)
    plt.close(fig)
    return out


def figure_fusion_modes():
    reports = {
        "stgcn": json.loads((PROC / "b6-comparison.json").read_text(encoding="utf-8")),
        "lstm": json.loads((PROC / "b6-comparison-lstm.json").read_text(encoding="utf-8")),
    }
    modes = ("rule_only", "model_only", "fusion_rule_gated", "fusion_model_led")
    mode_names = ["规则 only", "模型 only", "规则门控融合", "模型主导融合"]
    fig, axes = plt.subplots(1, 3, figsize=(13, 4), dpi=160)
    metrics = (
        ("fall_detected", "跌倒检出（/6）", 6),
        ("adl_false_alarms", "ADL 误报序列（/8）", 8),
        ("fall_p0", "P0 确认告警数", 6),
    )
    width = 0.36
    x = np.arange(len(modes))
    for ax, (field, title, total) in zip(axes, metrics):
        for offset, key in zip((-width / 2, width / 2), ("stgcn", "lstm")):
            values = [reports[key]["splits"]["test"][m][field] for m in modes]
            bars = ax.bar(x + offset, values, width=width, color=COLORS[key],
                          label=NAMES[key])
            for bar, value in zip(bars, values):
                ax.text(bar.get_x() + bar.get_width() / 2, value + 0.08, str(value),
                        ha="center", fontsize=8)
        ax.set_xticks(x, mode_names, rotation=18, ha="right", fontsize=9)
        ax.set_title(title)
        ax.set_ylim(0, total + 1)
        ax.grid(axis="y", alpha=0.3)
        ax.legend(fontsize=8)
    fig.suptitle("test 集四种检测模式的 ST-GCN vs LSTM 对比", fontsize=12)
    fig.tight_layout()
    out = FIG / "test_fusion_modes.png"
    fig.savefig(out)
    plt.close(fig)
    return out


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    models = {"stgcn": load_stgcn(device)[0], "lstm": load_lstm(device)[0]}
    data = {split: load_split(split) for split in ("val", "test")}
    thresholds = {
        "stgcn": float(json.loads(
            (PROC / "b6-comparison.json").read_text(encoding="utf-8"))["threshold"]),
        "lstm": float(json.loads(
            (PROC / "b6-comparison-lstm.json").read_text(encoding="utf-8"))["threshold"]),
    }
    outputs = [
        figure_split_overview(),
        figure_val_test_curves(models, data),
        figure_confusion(models, data, thresholds),
        figure_sequence_scores(models, data, thresholds),
        figure_fusion_modes(),
    ]
    for path in outputs:
        print(f"written {path}")


if __name__ == "__main__":
    main()
