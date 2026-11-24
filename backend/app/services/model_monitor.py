"""In-memory model runtime monitor.

Tracks recent inference scores and latency. A drift alert is raised when the
recent mean score moves more than three baseline standard deviations away from
the baseline mean. This is a lightweight runtime signal, not a replacement for
offline dataset shift analysis.
"""

from __future__ import annotations

import statistics
import threading
import time
from collections import deque
from typing import Any

MAX_RECORDS = 500
DEFAULT_BASELINE = {"score_mean": 0.5, "score_std": 0.2, "latency_p95_ms": 100.0}

_lock = threading.Lock()
_records: deque[dict[str, Any]] = deque(maxlen=MAX_RECORDS)
_baseline = dict(DEFAULT_BASELINE)


def configure_baseline(score_mean: float, score_std: float, latency_p95_ms: float) -> dict[str, float]:
    global _baseline
    if score_std <= 0:
        raise ValueError("score_std must be positive")
    with _lock:
        _baseline = {
            "score_mean": float(score_mean),
            "score_std": float(score_std),
            "latency_p95_ms": float(latency_p95_ms),
        }
        return dict(_baseline)


def record(device_no: str, score: float, latency_ms: float, level: str = "P1") -> None:
    if not 0.0 <= float(score) <= 1.0:
        raise ValueError("score must be between 0 and 1")
    if float(latency_ms) < 0:
        raise ValueError("latency_ms must be non-negative")
    with _lock:
        _records.append({
            "ts": time.time(),
            "deviceNo": device_no,
            "score": float(score),
            "latencyMs": float(latency_ms),
            "level": level,
        })


def reset() -> None:
    with _lock:
        _records.clear()


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * p)))
    return float(ordered[index])


def snapshot() -> dict[str, Any]:
    with _lock:
        items = list(_records)
        baseline = dict(_baseline)
    scores = [r["score"] for r in items]
    latencies = [r["latencyMs"] for r in items]
    mean = statistics.fmean(scores) if scores else 0.0
    std = statistics.pstdev(scores) if len(scores) > 1 else 0.0
    p95 = _percentile(latencies, 0.95)
    delta = mean - baseline["score_mean"]
    z_score = delta / baseline["score_std"] if baseline["score_std"] else 0.0
    alerts: list[str] = []
    if len(items) >= 20 and abs(z_score) >= 3:
        alerts.append("score_drift")
    if len(items) >= 20 and p95 > baseline["latency_p95_ms"]:
        alerts.append("latency_regression")
    return {
        "count": len(items),
        "baseline": baseline,
        "score": {"mean": round(mean, 4), "std": round(std, 4), "zScore": round(z_score, 3)},
        "latencyMs": {"p50": round(_percentile(latencies, 0.5), 2), "p95": round(p95, 2)},
        "alerts": alerts,
    }
