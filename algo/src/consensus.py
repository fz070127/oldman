"""Inference-time multi-window consensus for monocular fall detection.

A single high-scoring window is not enough to raise a fall event. The sequence
is triggered when at least `min_hits` windows inside a sliding window exceed
`threshold`. This is a deterministic post-processor; it does not train anything.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class ConsensusResult:
    triggered: bool
    first_window: int | None
    hit_count: int
    max_score: float
    # 窗口内第 min_hits 个命中所在窗口的全局索引，用于换算报警延迟；
    # first_window 只是滑动窗口起点，不能当作触发时刻。
    trigger_index: int | None = None


def moving_average_consensus(
    scores: Iterable[float],
    threshold: float,
    window: int = 3,
) -> ConsensusResult:
    """滑动平均时序聚合：连续 `window` 个窗口的平均分达到阈值才触发。

    与单窗越阈相比，孤立的高分尖峰不足以触发；该函数只需最近 `window`
    个分数，可在流式边缘端用 deque 直接实现，无需回看整段视频。
    """
    values = [float(s) for s in scores]
    if not values or window < 1:
        return ConsensusResult(False, None, 0, max(values, default=0.0))
    if len(values) < window:
        return ConsensusResult(False, None, 0, max(values))
    for start in range(len(values) - window + 1):
        segment = values[start:start + window]
        if sum(segment) / window >= threshold:
            return ConsensusResult(True, start, window, max(values), start + window - 1)
    return ConsensusResult(False, None, 0, max(values))


def sliding_consensus(
    scores: Iterable[float],
    threshold: float,
    window: int = 3,
    min_hits: int = 2,
) -> ConsensusResult:
    values = [float(s) for s in scores]
    if not values or window < 1 or min_hits < 1 or min_hits > window:
        return ConsensusResult(False, None, 0, max(values, default=0.0))
    hits = [s >= threshold for s in values]
    for start in range(len(hits)):
        segment = hits[start:start + window]
        count = sum(segment)
        if count >= min_hits:
            positions = [i for i, hit in enumerate(segment) if hit]
            index = start + positions[min_hits - 1]
            return ConsensusResult(True, start, count, max(values), index)
    return ConsensusResult(False, None, int(max(hits, default=False)), max(values))
