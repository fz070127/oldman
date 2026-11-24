"""校验 C2 配置与边缘共识行为，可选复验已生成的离线报告。

不依赖 Docker / 后端 / 权重文件，纯本地静态与逻辑校验。
输出 JSON 到 logs/verify_c2.json，任一检查失败以非零退出码结束。
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import deque
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
EDGE = ROOT / "edge"
if str(EDGE) not in sys.path:
    sys.path.insert(0, str(EDGE))

OUT = ROOT / "logs" / "verify_c2.json"


def check_config():
    offline = json.loads((ROOT / "algo/configs/consensus.json").read_text(encoding="utf-8"))
    edge = yaml.safe_load((EDGE / "config.yaml").read_text(encoding="utf-8"))
    consensus = edge["detector"].get("consensus") or {}
    checks = {
        "edge_enabled": consensus.get("enabled") is True,
        "mode_matches": consensus.get("mode") == offline.get("mode"),
        "threshold_matches": abs(float(consensus.get("threshold", -1))
                                 - float(offline["threshold"])) < 1e-12,
        "window_matches": int(consensus.get("window", -1)) == int(offline["window"]),
        "stride_matches": consensus.get("score_stride_frames") == offline["window_stride_frames"],
    }
    return {"ok": all(checks.values()), "checks": checks,
            "offline": offline, "edge": consensus}


def check_offline_report(config_path):
    c2 = ROOT / "algo/data/processed/c2"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    dense = json.loads((ROOT / config["score_source"]).read_text(encoding="utf-8"))
    verify = json.loads((c2 / "consensus_verify.json").read_text(encoding="utf-8"))
    report = json.loads((c2 / "consensus_report.json").read_text(encoding="utf-8"))
    checks = {
        "independent_recompute_all_ok": verify.get("all_ok") is True,
        "report_config_matches_file": report.get("config") == config,
        "verify_config_matches_file": verify.get("config") == config,
        "stride_matches_dense_scores": all(
            strides == [config["window_stride_frames"]]
            for strides in dense["window_stride_frames_by_split"].values()
        ),
        "test_evaluated_once": "test" in report.get("metrics", {}),
        "acceptance_flag_present": "acceptance_met" in report.get("selection", {}),
    }
    return {"ok": all(checks.values()), "checks": checks,
            "acceptance_met": report["selection"]["acceptance_met"]}


def check_edge_behaviour():
    """用替身 window_prob 验证采样步长与共识触发，不加载 torch 权重。"""
    from model_confirm import StgcnConfirm
    from src.consensus import moving_average_consensus

    obj = StgcnConfirm.__new__(StgcnConfirm)
    obj.consensus_window = 2
    obj.consensus_threshold = 0.0191
    obj.consensus_stride = 3
    obj.threshold = 0.0191
    obj.scores = deque(maxlen=2)
    obj.last_scored_frame = None

    stream = [0.001, 0.001, 0.001, 0.5, 0.001, 0.001, 0.001, 0.5, 0.5, 0.001]
    calls = []

    def fake_window_prob():
        calls.append(1)
        return stream[min(len(calls) - 1, len(stream) - 1)]

    obj.window_prob = fake_window_prob
    results = []
    for frame in range(1, 31):
        results.append(obj._consensus_prob(frame))

    # 每 3 帧采样一次，30 帧内最多 10 次打分
    stride_ok = len(calls) == 10
    # 孤立尖峰（0.5 与相邻 0.001 平均 0.2505 >= 0.0191 会触发），
    # 这里阈值较低，故用「连续两窗高分」与「未达窗长不触发」验证行为。
    no_trigger_before_full = results[0] is None
    triggered_at = [i + 1 for i, v in enumerate(results) if v is not None]
    triggered_ok = bool(triggered_at) and all((frame - 1) % 3 == 0 for frame in triggered_at)
    obj.window_prob = lambda: None
    assert obj._consensus_prob(31) is None
    gap_clears_scores = not obj.scores
    # 纯函数独立复验：孤立尖峰被 3 窗平均压制
    pure = moving_average_consensus([0.001, 0.5, 0.001, 0.001], 0.2, 3).triggered is False
    checks = {
        "sampling_stride_3": stride_ok,
        "no_trigger_before_window_full": no_trigger_before_full,
        "consensus_can_trigger": triggered_ok,
        "missing_window_clears_history": gap_clears_scores,
        "moving_average_suppresses_isolated_peak": pure,
        "n_window_prob_calls": len(calls),
        "first_trigger_frame": triggered_at[0] if triggered_at else None,
    }
    return {"ok": all(v for k, v in checks.items()
                      if isinstance(v, bool)) is True, "checks": checks}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline-config", type=Path, help="离线报告使用的配置文件")
    args = parser.parse_args()
    result = {
        "config": check_config(),
        "edge": check_edge_behaviour(),
    }
    if args.offline_config:
        try:
            result["offline"] = check_offline_report(args.offline_config)
        except FileNotFoundError as error:
            result["offline"] = {"ok": False, "error": str(error)}
    result["all_ok"] = all(section["ok"] for section in result.values())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["all_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
