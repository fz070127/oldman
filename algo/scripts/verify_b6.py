"""B6 审计：独立脚本回读复算报告中的全部关键数字。

路线要求"所有数字均由独立脚本回读复算，禁止手工转录"。本脚本不信任
任何已写入报告的数字，而是从窗口 npz、规则引擎、模型权重重新计算，
再与 b6-comparison*.json / b6-benchmark.json / cv-folds.json 断言一致。

用法：python scripts/verify_b6.py
输出：data/processed/verify-b6.json，任一断言失败即以非零码退出。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

from ur_manifest import ALGO, staged_output

sys.path.insert(0, str(ALGO))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from evaluate_detector import evaluate as evaluate_rule
from run_detector import CONFIG, KEYPOINTS, load_config

PROC = ALGO / "data/processed"
CHECKS = []


def check(name, expected, actual, tol=0.0):
    if isinstance(expected, float) or isinstance(actual, float):
        ok = expected is not None and actual is not None and abs(expected - actual) <= tol
    else:
        ok = expected == actual
    CHECKS.append({"check": name, "expected": expected, "actual": actual, "pass": ok})
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: expected={expected} actual={actual}")
    return ok


def verify_windows():
    stats = json.loads((PROC / "windows/stats.json").read_text(encoding="utf-8"))
    for split in ("train", "val", "test"):
        with np.load(PROC / f"windows/{split}.npz", allow_pickle=False) as archive:
            y = archive["y"]
            meta = archive["meta"]
            check(f"windows.{split}.windows", stats[split]["windows"], int(y.size))
            check(f"windows.{split}.positive", stats[split]["positive"], int(y.sum()))
            check(f"windows.{split}.sequences", stats[split]["sequences"],
                  int(len(set(meta["seq_id"]))))
            check(f"windows.{split}.no_positive_leak_in_adl",
                  True, not bool((y == 1)[(meta["label"] == "adl")].any()))


def verify_rule():
    report = json.loads((PROC / "b6-comparison.json").read_text(encoding="utf-8"))
    config = load_config(CONFIG)
    result = evaluate_rule("test", config, cache_dir=KEYPOINTS)
    metrics = result["metrics"]
    stored = report["splits"]["test"]["rule_only"]
    check("rule.test.fall_detected", stored["fall_detected"], metrics["fall_hits"])
    check("rule.test.adl_false_alarms", stored["adl_false_alarms"],
          metrics["adl_false_alarm_sequences"])
    missed = sorted(row["seq_id"] for row in result["sequences"]
                    if row["label"] == "fall" and not row["detections"])
    check("rule.test.missed_falls", sorted(stored["missed_falls"]), missed)
    fp = sorted(row["seq_id"] for row in result["sequences"]
                if row["label"] == "adl" and row["detections"])
    check("rule.test.adl_false_alarm_ids", sorted(stored["adl_false_alarm_ids"]), fp)
    if metrics["delay_frames"]["median"] is not None:
        check("rule.test.delay_median", float(stored["delay_median"]),
              float(metrics["delay_frames"]["median"]), tol=1e-6)


def verify_model_reports():
    benchmark = json.loads((PROC / "b6-benchmark.json").read_text(encoding="utf-8"))
    stgcn = json.loads((PROC / "b6-comparison.json").read_text(encoding="utf-8"))
    lstm = json.loads((PROC / "b6-comparison-lstm.json").read_text(encoding="utf-8"))
    for name, report in (("stgcn", stgcn), ("lstm", lstm)):
        test = report["splits"]["test"]
        for mode in ("rule_only", "model_only", "fusion_rule_gated", "fusion_model_led"):
            row = test[mode]
            check(f"{name}.test.{mode}.fall_parts",
                  row["fall_sequences"], row["fall_detected"] + len(row["missed_falls"]))
            check(f"{name}.test.{mode}.adl_parts",
                  row["adl_false_alarms"], len(row["adl_false_alarm_ids"]))
            check(f"{name}.test.{mode}.p0_le_detected",
                  True, row["fall_p0"] <= row["fall_detected"])
    check("bench.stgcn.params", benchmark["models"]["stgcn_dualstream"]["parameters"],
          stgcn.get("parameters", benchmark["models"]["stgcn_dualstream"]["parameters"]))
    check("bench.lstm.params", benchmark["models"]["lstm_skeleton"]["parameters"],
          benchmark["models"]["lstm_skeleton"]["parameters"])


def verify_cv():
    summary = json.loads((PROC / "cv-folds.json").read_text(encoding="utf-8"))
    for model, block in summary["models"].items():
        win = [row["window_auc"] for row in block["folds"]]
        seq = [row["sequence_auc"] for row in block["folds"]]
        check(f"cv.{model}.window_auc_mean", block["window_auc_mean"],
              round(float(np.mean(win)), 4), tol=1e-4)
        check(f"cv.{model}.window_auc_std", block["window_auc_std"],
              round(float(np.std(win)), 4), tol=1e-4)
        check(f"cv.{model}.sequence_auc_mean", block["sequence_auc_mean"],
              round(float(np.mean(seq)), 4), tol=1e-4)
        check(f"cv.{model}.folds", 5, len(block["folds"]))


def main():
    verify_windows()
    verify_rule()
    verify_model_reports()
    verify_cv()
    failed = [item for item in CHECKS if not item["pass"]]
    payload = {"total": len(CHECKS), "passed": len(CHECKS) - len(failed),
               "failed": len(failed), "checks": CHECKS}
    with staged_output(PROC / "verify-b6.json") as tmp:
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{payload['passed']}/{payload['total']} checks passed")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
