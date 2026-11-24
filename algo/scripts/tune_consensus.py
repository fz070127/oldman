"""C2: 只在 val 上搜索多窗共识参数，冻结后对 test 评估一次。

判定方式为「滑动平均时序聚合」：连续 window 个 ST-GCN 窗口分数的均值
达到 threshold 才触发，用于压制孤立高分窗口。分数来自 stride=3 的稠密
滑窗（dump_dense_scores.py），同一冻结权重、同一批关键点。

约束（对应 docs/C_EXECUTION_PLAN.md）：
- 参数候选全部由 val 分段分数生成；test 不参与任何筛选或择优。
- 单窗越阈作为受控基线，与共识使用同一份分数、同一个阈值。
- 报警延迟按窗口结束帧减 fall_onset 计算，只统计清单中确有人工 onset 的段。
- 没有实测的指标写 None / n/a，不用估计值补齐。
"""

from __future__ import annotations

import argparse
import json
import sys
from itertools import product
from pathlib import Path

import numpy as np

from ur_manifest import ALGO, staged_output

if str(ALGO) not in sys.path:
    sys.path.insert(0, str(ALGO))
from src.consensus import moving_average_consensus

SCORES = ALGO / "data/processed/c2/sequence_scores_dense.json"
CONFIG = ALGO / "configs/consensus.json"
OUT = ALGO / "data/processed/c2/consensus_report.json"
B6_THRESHOLD = 0.0191
WINDOW_CANDIDATES = tuple(range(2, 13))
QUANTILES = (1, 5, 10, 15, 20, 25, 30, 40, 50, 60, 70, 75, 85, 90, 95, 98, 99, 99.5)


def threshold_candidates(sequences):
    """阈值网格由 val 逐窗分数分位数生成，另并入 B6 冻结阈值。"""
    values = np.array([s for seq in sequences for s in seq["scores"]], dtype=float)
    grid = {round(float(v), 9) for v in np.percentile(values, QUANTILES)}
    grid.add(round(B6_THRESHOLD, 9))
    return sorted(v for v in grid if v > 0)


def first_hit_index(scores, threshold):
    for index, score in enumerate(scores):
        if score >= threshold:
            return index
    return None


def summarize(sequences, mode, threshold, window):
    fall_hits, adl_hits, delays = [], [], []
    for seq in sequences:
        if mode == "consensus":
            result = moving_average_consensus(seq["scores"], threshold, window)
            index = result.trigger_index if result.triggered else None
        else:
            index = first_hit_index(seq["scores"], threshold)
        if index is None:
            continue
        if seq["label"] == "fall":
            fall_hits.append(seq["seq_id"])
        else:
            adl_hits.append(seq["seq_id"])
        if seq["label"] == "fall" and seq.get("onset") is not None:
            ends = seq.get("window_end_frames") or []
            if index < len(ends):
                delays.append(int(ends[index]) - int(seq["onset"]))
    falls = [s for s in sequences if s["label"] == "fall"]
    adls = [s for s in sequences if s["label"] != "fall"]
    return {
        "fall_sequences": len(falls),
        "fall_detected": len(fall_hits),
        "fall_detection_rate": round(len(fall_hits) / len(falls), 4) if falls else None,
        "adl_sequences": len(adls),
        "adl_false_alarms": len(adl_hits),
        "adl_p0": 0,
        "fall_hit_ids": fall_hits,
        "adl_false_alarm_ids": adl_hits,
        "delay_frames": delays,
        "delay_median": float(np.median(delays)) if delays else None,
        "delay_sec": [round(d / 30, 3) for d in delays],
        "delay_sample_note": "仅统计 ur_fall.csv 中带人工 fall_onset 的跌倒段",
        "adl_p0_note": "多窗共识为 P1 级后处理，本身不产生 P0；P0 由规则确认路径决定",
    }


def objective(metrics):
    """与 B6 校准一致：最大化（跌倒检出段数 - ADL 误报段数）。"""
    return metrics["fall_detected"] - metrics["adl_false_alarms"]


def rank_key(row):
    m = row["val"]
    delay = m["delay_median"]
    return (
        objective(m),
        -m["adl_false_alarms"],
        m["fall_detected"],
        -abs(delay) if delay is not None else -1e9,
        row["threshold"],
        row["window"],
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scores", type=Path, default=SCORES)
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--sweep-only", action="store_true",
                        help="只输出 val 网格结果，不写配置、不评估 test")
    args = parser.parse_args()

    payload = json.loads(args.scores.read_text(encoding="utf-8"))
    sequences = payload["sequences"]
    val = [s for s in sequences if s["split"] == "val"]
    test = [s for s in sequences if s["split"] == "test"]
    thresholds = threshold_candidates(val)

    grid = []
    for threshold, window in product(thresholds, WINDOW_CANDIDATES):
        metrics = summarize(val, "consensus", threshold, window)
        grid.append({"threshold": threshold, "window": window,
                     "val": metrics, "val_objective": objective(metrics)})

    n_val_fall = sum(1 for s in val if s["label"] == "fall")
    n_val_adl = sum(1 for s in val if s["label"] != "fall")
    accepted = [r for r in grid
                if r["val"]["fall_detected"] == n_val_fall
                and r["val"]["adl_false_alarms"] < 2]
    pool = accepted or grid
    best = max(pool, key=rank_key)
    config = {
        "name": "c2-val-tuned-moving-average",
        "mode": "moving_average",
        "threshold": best["threshold"],
        "window": best["window"],
        "score_source": str(args.scores.resolve()
                            .relative_to(ALGO.parent)).replace("\\", "/"),
        "window_stride_frames": int(val[0]["window_stride_frames"]),
        "window_length_frames": payload.get("window_length_frames", 30),
        "note": ("由 tune_consensus.py 在 val 上网格搜索得出；test 仅冻结后评估一次。"
                 "同一冻结 ST-GCN 权重，仅改变滑窗步长与后处理，不重训、不覆盖 B 阶段产物。"),
        "acceptance_met": bool(accepted),
    }
    selection = {
        "method": "val-only grid search; objective = fall_detected - adl_false_alarms",
        "decision": "moving_average_consensus（连续 window 窗均分达到 threshold 才触发）",
        "why_dense_scores": ("stride=15 冻结窗口上多窗硬计数无法同时保住检出率与误报；"
                             "stride=3 稠密滑窗提供足够时间分辨率，且不改动冻结窗口文件"),
        "thresholds": thresholds,
        "window_candidates": list(WINDOW_CANDIDATES),
        "n_candidates": len(grid),
        "acceptance_rule": f"val 检出 {n_val_fall}/{n_val_fall} 且 ADL 误报 < 2/{n_val_adl}",
        "n_acceptance_candidates": len(accepted),
        "acceptance_met": bool(accepted),
        "fallback_to_plain_objective": not bool(accepted),
        "best_val": best,
        "top_candidates": sorted(grid, key=rank_key, reverse=True)[:10],
    }

    report = {
        "config": config,
        "source": str(args.scores),
        "selection": selection,
        "metrics": {"train": "not_evaluated（train 用于训练，不参与 C2 调参）"},
        "controlled_comparison": {},
    }
    if not args.sweep_only:
        report["metrics"]["val"] = summarize(
            val, "consensus", config["threshold"], config["window"])
        report["metrics"]["test"] = summarize(
            test, "consensus", config["threshold"], config["window"])
        for split, rows in (("val", val), ("test", test)):
            report["controlled_comparison"][split] = {
                "single_window_baseline": summarize(rows, "single", config["threshold"], 1),
                "multi_window_consensus": report["metrics"][split],
                "note": "两者使用同一份稠密分数与同一阈值，差异仅来自多窗聚合",
            }

    with staged_output(args.output) as tmp:
        tmp.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not args.sweep_only:
        with staged_output(args.config) as tmp:
            tmp.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    test_metrics = None if args.sweep_only else report["metrics"]["test"]
    print(json.dumps({
        "n_candidates": len(grid),
        "acceptance_met": bool(accepted),
        "best": {k: best[k] for k in ("threshold", "window", "val_objective")},
        "val": {k: best["val"][k] for k in
                ("fall_detected", "adl_false_alarms", "delay_median")},
        "val_single_window": None if args.sweep_only else {
            k: report["controlled_comparison"]["val"]["single_window_baseline"][k]
            for k in ("fall_detected", "adl_false_alarms")},
        "test": None if test_metrics is None else {
            k: test_metrics[k] for k in ("fall_detected", "adl_false_alarms", "delay_median")},
        "test_single_window": None if args.sweep_only else {
            k: report["controlled_comparison"]["test"]["single_window_baseline"][k]
            for k in ("fall_detected", "adl_false_alarms")},
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
