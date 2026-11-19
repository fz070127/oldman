"""从腰部 IMU 找候选峰，并记录视频逐帧复核结果。"""

import argparse
import csv
from pathlib import Path

import numpy as np

from ur_manifest import ALGO, MANIFEST, read_manifest, staged_output, write_csv

EXTRA = ALGO.parent / "sumanpunshi/ur-fall-extra"
REPORT = ALGO / "reports/onset_annotation.md"
REVIEWS = ALGO / "reports/onset_review.csv"


def candidate(row):
    seq = row["seq_id"]
    acc = np.loadtxt(EXTRA / f"{seq}-acc.csv", delimiter=",", ndmin=2)
    aligned = np.loadtxt(EXTRA / f"{seq}-data.csv", delimiter=",", ndmin=2)
    if (acc.shape[1] != 5 or aligned.shape != (int(row["frame_count"]), 3)
            or not np.isfinite(acc).all() or not np.isfinite(aligned).all()
            or not np.array_equal(aligned[:, 0], np.arange(1, len(aligned) + 1))
            or np.any(np.diff(aligned[:, 1]) <= 0) or np.any(np.diff(acc[:, 0]) <= 0)):
        raise ValueError(f"{seq}: 加速度或帧对齐表格式错误")
    times = acc[1:, 0]
    delta = np.abs(np.diff(acc[:, 1]))
    available = np.flatnonzero((times >= aligned[0, 1]) & (times <= aligned[-1, 1]))
    if not len(available):
        raise ValueError(f"{seq}: 对齐范围内没有加速度样本")
    peak = available[np.argmax(delta[available])]
    frame = np.interp(times[peak], aligned[:, 1], aligned[:, 0])
    return int(np.floor(frame + 0.5)), int(times[peak]), float(delta[peak])


def read_reviews(path, rows):
    reviews = {}
    if path.exists():
        with path.open(encoding="utf-8-sig", newline="") as f:
            for record in csv.DictReader(f):
                seq = record["seq_id"]
                if seq in reviews or seq not in rows or rows[seq]["label"] != "fall":
                    raise ValueError(f"{seq}: 无效或重复复核记录")
                frame = int(record["frame"])
                if not 1 <= frame <= int(rows[seq]["frame_count"]) or not record["basis"].strip():
                    raise ValueError(f"{seq}: 复核帧或观察记录无效")
                if record["review"] not in ("未人工逐帧复核", "人工逐帧复核"):
                    raise ValueError(f"{seq}: 复核状态无效")
                if record["approved"] not in ("0", "1"):
                    raise ValueError(f"{seq}: 登记授权须为 0 或 1")
                uncertainty = record["uncertainty_frames"]
                if uncertainty and (not uncertainty.isdigit() or int(uncertainty) <= 0):
                    raise ValueError(f"{seq}: 帧不确定度无效")
                reviews[seq] = record
    return reviews


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reviews", type=Path, default=REVIEWS)
    parser.add_argument("--apply", action="store_true", help="将人工复核登记的视觉判读值写入总清单")
    args = parser.parse_args()
    rows = read_manifest()
    reviews = read_reviews(args.reviews, rows)
    lines = ["# 跌倒起始帧标注", "",
             "fall_onset 定义为人体开始失去平衡的第一帧，以 1 起算。"
             "A4 计算时延时使用人工复核登记的视觉判读帧，并保留实际复核来源与边界不确定度。",
             "", "对齐表的三列为帧号、毫秒时间戳和插值加速度，没有事件标签。"
             "在 RGB 时间范围内取腰部 SVector 绝对一阶差分的最强峰，以差分末端采样时刻做线性插值并四舍五入到帧。"
             "冲击、扶撑、先行步态或缓慢滑倒都会使最强峰偏离失衡起点。",
             "", "复核视频由 preview.py 从 cam0 PNG 合成。以躯干偏移、支撑失稳及随后连续下坠为视觉依据。"
             "auto_onset 为 IMU 自动候选。人工复核确认前十段写入 fall_onset，其中六段经人工逐帧复核。"
             "其余二十段跌倒仅保留自动值。40 段 ADL 的 fall_onset 留空。", "",
             "|段号|峰时刻 ms|峰值差分|auto_onset|视频判读帧|判读减候选（帧）|不确定度|review|观察与修正记录|",
             "|---|---:|---:|---:|---:|---:|---|---|---|"]
    changed = 0
    for seq, row in rows.items():
        if row["label"] != "fall":
            continue
        frame, ms, strength = candidate(row)
        review = reviews.get(seq)
        visual, diff, status, uncertainty, basis = "—", "—", "待复核", "—", "—"
        label = seq
        if review:
            label = f"[{seq}](../data/processed/clips/{seq}.mp4)"
            visual = review["frame"]
            diff = str(int(visual) - frame)
            status, basis = review["review"], review["basis"]
            uncertainty = (f"±{review['uncertainty_frames']} 帧"
                           if review["uncertainty_frames"] else "未量化")
            if args.apply and review["approved"] == "1" and row["fall_onset"] != visual:
                row["fall_onset"] = visual
                changed += 1
        lines.append(f"|{label}|{ms}|{strength:.4f}|{frame}|{visual}|{diff}|{uncertainty}|{status}|{basis}|")
    lines += ["", f"视频判读 {len(reviews)} 段，总清单已登记 "
              f"{sum(bool(r['fall_onset']) for r in rows.values() if r['label'] == 'fall')} 段。"]
    if changed:
        write_csv(MANIFEST, rows.values())
    with staged_output(REPORT) as tmp:
        tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
