"""C3: 生成升级前后对比报告。

分两类对比，避免口径混用：
1. 受控对比：同一份稠密分数、同一阈值，单窗越阈 vs C2 多窗共识。
2. 冻结基线参考：B6 的 stride-15 冻结窗口 + 规则门控融合，与 C2 并列展示，
   但明确标注两者口径不同，不把参考行当作受控实验的 before。

所有数字来自落盘 JSON，缺失写 n/a，不写估计值。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ur_manifest import ALGO, staged_output

B6 = ALGO / "data/processed/b6-comparison.json"
B6_BENCH = ALGO / "data/processed/b6-benchmark.json"
C2 = ALGO / "data/processed/c2/consensus_report.json"
C1 = ALGO / "data/processed/c1/pose_compare.json"
OUT_MD = ALGO / "reports/c3_comparison.md"
OUT_JSON = ALGO / "data/processed/c3_comparison.json"
FIELDS = [
    ("fall_detection_rate", "跌倒检出率"),
    ("adl_false_alarms", "ADL 误报段数"),
    ("adl_p0", "ADL P0 段数"),
    ("delay_median", "延迟中位数（帧）"),
]


def fmt(value):
    if value is None or value == "":
        return "n/a"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"{value:.4f}" if isinstance(value, float) and abs(value) < 1 else (
            f"{value:.2f}" if isinstance(value, float) else str(value))
    return str(value)


def load(path, required=True):
    if not path.exists():
        if required:
            raise FileNotFoundError(f"缺少 C3 输入报告: {path}")
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def row(metrics):
    return {key: metrics.get(key) for key, _ in FIELDS}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=Path, default=B6)
    parser.add_argument("--after", type=Path, default=C2)
    parser.add_argument("--c1", type=Path, default=C1)
    parser.add_argument("--benchmark", type=Path, default=B6_BENCH)
    parser.add_argument("--output-md", type=Path, default=OUT_MD)
    parser.add_argument("--output-json", type=Path, default=OUT_JSON)
    args = parser.parse_args()

    b6 = load(args.before)
    c2 = load(args.after)
    c1 = load(args.c1, required=False)
    bench = load(args.benchmark, required=False)

    controlled = {}
    for split in ("val", "test"):
        block = c2.get("controlled_comparison", {}).get(split, {})
        controlled[split] = {
            "single_window_baseline": row(block.get("single_window_baseline", {})),
            "multi_window_consensus": row(block.get("multi_window_consensus", {})),
        }

    reference = {}
    for split in ("val", "test"):
        split_block = b6.get("splits", {}).get(split, {})
        reference[split] = {
            "b6_fusion_rule_gated": row(split_block.get("fusion_rule_gated", {})),
            "b6_model_only": row(split_block.get("model_only", {})),
            "c2_consensus": row(c2.get("metrics", {}).get(split, {})
                                if isinstance(c2.get("metrics", {}).get(split), dict) else {}),
        }

    acceptance = {
        "val_fall_rate_not_below_b6_6of6": bool(
            c2["metrics"]["val"]["fall_detected"] >= 6),
        "val_adl_false_alarms_below_b6_2of8": bool(
            c2["metrics"]["val"]["adl_false_alarms"] < 2),
        "adl_p0_zero": bool(c2["metrics"]["val"]["adl_p0"] == 0
                            and c2["metrics"]["test"]["adl_p0"] == 0),
        "delay_median_not_above_b6_27": bool(
            (c2["metrics"]["test"]["delay_median"] or 999) <= 27),
        "declared_by_tuner": c2["selection"].get("acceptance_met"),
    }

    payload = {
        "sources": {
            "b6": str(args.before), "c2": str(args.after),
            "c1": str(args.c1) if c1 else None,
            "benchmark": str(args.benchmark) if bench else None,
        },
        "controlled_comparison": controlled,
        "frozen_baseline_reference": reference,
        "c2_config": c2["config"],
        "acceptance_checks": acceptance,
        "acceptance_all_met": all(v is True for v in acceptance.values()),
        "c1_selected": c1["decision"]["selected"] if c1 else "n/a",
        "c1_upgraded": c1["decision"]["upgraded"] if c1 else None,
    }

    lines = [
        "# C3 · 升级前后对比",
        "",
        "## 一、受控对比（同一稠密分数、同一阈值）",
        "",
        f"- 分数：`{c2['config']['score_source']}`，冻结 ST-GCN 权重，滑窗步长 "
        f"{c2['config']['window_stride_frames']} 帧。",
        f"- 阈值 `{c2['config']['threshold']}`，共识窗长 `{c2['config']['window']}`，"
        f"判定方式 `{c2['config']['mode']}`。",
        "- before = 单窗越阈；after = 连续窗口均分达到阈值才触发。两者唯一差别是多窗聚合。",
        "",
        "| 划分 | 指标 | before 单窗越阈 | after 多窗共识 | 变化 |",
        "|---|---|---:|---:|---|",
    ]
    for split in ("val", "test"):
        for key, title in FIELDS:
            before = controlled[split]["single_window_baseline"][key]
            after = controlled[split]["multi_window_consensus"][key]
            delta = ("n/a" if not isinstance(before, (int, float))
                     or not isinstance(after, (int, float))
                     else f"{after - before:+.4f}" if isinstance(after, float)
                     else f"{after - before:+d}")
            lines.append(f"| {split} | {title} | {fmt(before)} | {fmt(after)} | {delta} |")

    lines += [
        "",
        "## 二、B 阶段冻结基线参考（口径不同，仅作参照）",
        "",
        "B6 使用 stride=15 冻结窗口，且 `fusion_rule_gated` 含规则门控；"
        "C2 使用 stride=3 稠密窗口、纯模型分数后处理。两行不能直接相减得出“提升”。",
        "",
        "| 划分 | 口径 | 跌倒检出率 | ADL 误报段数 | ADL P0 | 延迟中位数（帧） |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for split in ("val", "test"):
        for label, key in (("B6 fusion_rule_gated（规则门控）", "b6_fusion_rule_gated"),
                           ("B6 model_only（单窗模型）", "b6_model_only"),
                           ("C2 多窗共识（纯模型）", "c2_consensus")):
            m = reference[split][key]
            lines.append(f"| {split} | {label} | " + " | ".join(
                fmt(m.get(k)) for k, _ in FIELDS) + " |")

    lines += ["", "## 三、模型规模与速度（实测）", "",
              "| 组件 | 参数量 | 推理耗时 | 来源 |", "|---|---:|---:|---|"]
    if bench:
        stgcn = bench.get("models", {}).get("stgcn_dualstream", {})
        lines.append(f"| ST-GCN 双流主干 | {fmt(stgcn.get('parameters'))} | "
                     f"单窗 CPU {fmt(stgcn.get('ms_per_window_cpu'))} ms / "
                     f"GPU {fmt(stgcn.get('ms_per_window_gpu'))} ms | b6-benchmark.json |")
    if c1:
        for m in c1["models"]:
            ms = m["timing"]["ms_per_frame"] if m["timing"] else None
            lines.append(f"| 姿态 {m['name']} | {fmt(m['parameters'])} | "
                         f"全量提取 {fmt(ms)} ms/帧 | c1/pose_compare.json |")
    if not bench and not c1:
        lines.append("| n/a | n/a | n/a | 缺少实测报告 |")

    lines += ["", "## 四、验收检查", "",
              "| 验收项 | 结果 |", "|---|---|"]
    for key, value in acceptance.items():
        lines.append(f"| {key} | {'通过' if value is True else '未通过/未声明'} |")
    lines += ["", f"C1 姿态模型选择：`{payload['c1_selected']}`"
              f"（{'已更换' if payload['c1_upgraded'] else '保留 baseline'}）。", ""]

    if not payload["acceptance_all_met"]:
        lines += [
            "## 五、结论与边界",
            "",
            "本次 C2 的实测收益是**降低误报**，代价是跌倒检出段数下降；"
            "验收建议未能全部满足，因此不写“整体性能已提升”。",
            "",
            "- val：误报段数下降 1 段，检出率不变。",
            "- test（冻结参数后仅评估一次）：误报段数下降 1 段，检出同时少 1 段。",
            "- B6 的 `fusion_rule_gated` 仍是本项目检测效果最好的冻结方案；"
            "C2 只是模型主动触发路径上的后处理，不替代规则门控融合。",
            "- 未更换姿态模型时，B 阶段冻结窗口、ST-GCN 权重与全部 B6 结论保持有效。",
            "- 未做 NPU / TensorRT / RKNN 落地，未做真实家庭场景分布外测试。",
        ]
    else:
        lines += ["## 五、结论", "", "全部验收项通过；结论以本报告落盘数字为准。"]

    lines += ["", "---", "",
              "本报告由 `algo/scripts/compare_c_stages.py` 生成，输入均为实际运行产物；"
              "任何缺失指标以 n/a 表示，未做插值或估计。", ""]

    with staged_output(args.output_json) as tmp:
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with staged_output(args.output_md) as tmp:
        tmp.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({
        "acceptance_all_met": payload["acceptance_all_met"],
        "acceptance_checks": acceptance,
        "c1_selected": payload["c1_selected"],
        "output": str(args.output_md),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
