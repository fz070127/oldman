"""C2 独立复验：按冻结配置重算共识指标，与 tune_consensus.py 的报告逐项比对。

本脚本不调参、不写配置、不看 test 之外的信息；只验证最终落盘的配置与
报告是否可复现。任何不一致都以非零退出码失败。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ur_manifest import ALGO, staged_output

if str(ALGO) not in sys.path:
    sys.path.insert(0, str(ALGO))
from src.consensus import moving_average_consensus

CONFIG = ALGO / "configs/consensus.json"
REPORT = ALGO / "data/processed/c2/consensus_report.json"
OUT = ALGO / "data/processed/c2/consensus_verify.json"
KEYS = ("fall_detected", "adl_false_alarms", "fall_detection_rate",
        "delay_median", "fall_hit_ids", "adl_false_alarm_ids")


def recompute(sequences, threshold, window):
    fall_hits, adl_hits, delays = [], [], []
    for seq in sequences:
        result = moving_average_consensus(seq["scores"], threshold, window)
        if not result.triggered:
            continue
        (fall_hits if seq["label"] == "fall" else adl_hits).append(seq["seq_id"])
        if seq["label"] == "fall" and seq.get("onset") is not None:
            ends = seq.get("window_end_frames") or []
            index = result.trigger_index
            if index is not None and index < len(ends):
                delays.append(int(ends[index]) - int(seq["onset"]))
    falls = [s for s in sequences if s["label"] == "fall"]
    adls = [s for s in sequences if s["label"] != "fall"]
    import statistics
    return {
        "fall_detected": len(fall_hits),
        "adl_false_alarms": len(adl_hits),
        "fall_detection_rate": round(len(fall_hits) / len(falls), 4) if falls else None,
        "delay_median": float(statistics.median(delays)) if delays else None,
        "fall_hit_ids": fall_hits,
        "adl_false_alarm_ids": adl_hits,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    config = json.loads(args.config.read_text(encoding="utf-8"))
    report = json.loads(args.report.read_text(encoding="utf-8"))
    # score_source 按项目根目录相对书写，便于离线脚本与边缘校验共用。
    scores_path = ALGO.parent / config["score_source"]
    payload = json.loads(scores_path.read_text(encoding="utf-8"))

    checks = {}
    all_ok = True
    for split in ("val", "test"):
        rows = [s for s in payload["sequences"] if s["split"] == split]
        actual = recompute(rows, float(config["threshold"]), int(config["window"]))
        expected = report["metrics"][split]
        diffs = {k: {"report": expected.get(k), "recomputed": actual.get(k)}
                 for k in KEYS if expected.get(k) != actual.get(k)}
        checks[split] = {"ok": not diffs, "diffs": diffs, "recomputed": actual}
        all_ok = all_ok and not diffs

    result = {
        "config": config,
        "scores": config["score_source"],
        "report": str(args.report),
        "checks": checks,
        "all_ok": all_ok,
    }
    with staged_output(args.output) as tmp:
        tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"all_ok": all_ok,
                      "splits": {k: v["ok"] for k, v in checks.items()},
                      "diffs": {k: v["diffs"] for k, v in checks.items() if v["diffs"]}},
                     ensure_ascii=False, indent=2))
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
