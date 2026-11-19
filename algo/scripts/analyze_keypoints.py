"""分析姿态可用性、连续漏检和多人帧，并生成 A2 质量报告。"""

import json

import numpy as np

from annotate_onset import REVIEWS, candidate, read_reviews
from extract_keypoints import OUT, validate
from ur_manifest import ALGO, read_manifest, staged_output


def zero_runs(counts):
    padded = np.r_[False, counts == 0, False].astype(int)
    changes = np.diff(padded)
    for start, stop in zip(np.flatnonzero(changes == 1), np.flatnonzero(changes == -1), strict=True):
        if stop - start >= 30:
            yield int(start + 1), int(stop)


def windows(values, anchor):
    # anchor 为 1 起帧号，两窗均排除中心帧，在序列边界截断。
    return values[max(0, anchor - 31):anchor - 1], values[anchor:anchor + 30]


def mean(x):
    return float(np.mean(x)) if len(x) else float("nan")


def main():
    rows = read_manifest()
    reviews = read_reviews(REVIEWS, rows)
    detail, windows_table, missing, tails = [], [], [], []
    before, after, visual_before, lying = [], [], [], []
    lying_frames = lying_empty = lying_weak = 0
    truncated = 0
    for seq, row in rows.items():
        n = int(row["frame_count"])
        path = OUT / f"{seq}.npz"
        validate(path, seq, n)
        with np.load(path, allow_pickle=False) as archive:
            people = archive["n_people"]
            conf = archive["kpts_conf"][:, 0].mean(axis=1)
        detail.append((seq, n, people.mean(), conf.mean(), sum(people > 0),
                       sum(conf < 0.3), sum(people >= 2)))
        missing.extend((seq, start, stop) for start, stop in zero_runs(people))
        if row["label"] != "fall":
            continue
        anchor, _, _ = candidate(row)
        pre, post = windows(conf, anchor)
        pb, pa = windows(people, anchor)
        if not len(pre) or not len(post):
            raise ValueError(f"{seq}: 对齐峰前后窗口为空")
        truncated += len(pre) < 30 or len(post) < 30
        before.append(mean(pre))
        after.append(mean(post))
        windows_table.append(f"|{seq}|{anchor}|{len(pre)}/{len(post)}|{mean(pb):.2f}|{mean(pa):.2f}|"
                             f"{mean(pb)-mean(pa):+.2f}|{mean(pre):.3f}|{mean(post):.3f}|"
                             f"{mean(pre)-mean(post):+.3f}|")
        review = reviews.get(seq)
        if review and review.get("lying_from"):
            first = int(review["lying_from"])
            onset = int(review["frame"])
            if not 1 < onset < first <= n:
                raise ValueError(f"{seq}: 视频判读区间错误")
            pre_visual = windows(conf, onset)[0]
            tail = conf[first-1:]
            lying_frames += len(tail)
            lying_empty += int(np.count_nonzero(people[first-1:] == 0))
            lying_weak += int(np.count_nonzero(tail < 0.3))
            visual_before.append(mean(pre_visual))
            lying.append(mean(tail))
            tails.append(f"|{seq}|{onset}|{len(pre_visual)}|{first}–{n}|{mean(pre_visual):.3f}|"
                         f"{mean(tail):.3f}|{mean(people[first-1:] > 0):.1%}|")
    total = sum(r[1] for r in detail)
    detected = sum(r[4] for r in detail)
    low = sum(r[5] for r in detail)
    multiple = sum(r[6] for r in detail)
    avg_people = sum(r[1]*r[2] for r in detail)/total
    avg_conf = sum(r[1]*r[3] for r in detail)/total
    timing_path = OUT.parent / "extraction_time.json"
    timing_text = "分批产物暂无完整运行计时。可通过全量提取命令实测端到端耗时。"
    if timing_path.exists():
        timing = json.loads(timing_path.read_text(encoding="utf-8"))
        if (timing["sequences"], timing["frames"]) != (len(rows), total):
            raise ValueError("耗时记录与本次全量数据不符")
        timing_text = (f"{timing['workers']} 个序列进程，全量墙钟耗时 {timing['wall_sec']:.2f} 秒，"
                       f"平均 {timing['ms_per_frame']:.2f} 毫秒/帧"
                       "（含模型加载、读图、推理、写盘和校验）。")
    direction = "降到" if mean(after) < mean(before) else "升到"
    impact = f"30 段 IMU 峰前后关键点平均置信度从 {mean(before):.3f} {direction} {mean(after):.3f}"
    decision = ("可进入 A3 原型验证" if detected and mean(after) >= .3
                else "暂缓依赖倒地姿态的 A3 验证")
    conclusion = f"{decision}。{impact}。"
    if lying:
        conclusion += (f"视频目检的 {len(lying)} 段，失衡前为 {mean(visual_before):.3f}，"
                       f"明确卧地时为 {mean(lying):.3f}。")
    conclusion += f"全量低置信帧占 {low/total:.1%}；仅凭骨架缺失无法确认跌倒后静止。"
    lines = ["# 关键点提取质量报告", "", "## 结论", "", conclusion, "",
             "## Q1 跌倒前后对比", "",
             "每段以腰部 SVector 差分峰经时间戳插值得到的 RGB 帧为中心，前后各取最多 30 帧，排除中心帧。"
             "峰值提供可复算的时刻参照，可能对应触地、撑地或其他动作。"
             f"共有 {truncated} 段窗口因视频边界而不足 30 帧。每帧取最高检测分人体的 17 点置信度均值，"
             "无检测帧记 0；Q1 汇总时每段等权。人数使用截取两槽之前的实际检测数。",
             "", "|段号|对齐峰帧|前/后帧数|前人数|后人数|人数下降|前置信度|后置信度|置信度下降|",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|", *windows_table, "",
             impact + "。下降列为前减后，负值表示上升。", ""]
    if tails:
        lines += ["### 视频可见的卧地帧", "",
                  "逐段目检 cam0 预览，另取明确卧地起至片尾的连续帧，与视觉失衡起始前最多 30 帧比较。"
                  "此处的“检出”只表示画面中有人；多人帧最高分槽可能切换对象。"
                  "样本取清单前十段。失衡起始帧由人工复核登记，其中六段经人工逐帧复核，四段未经人工逐帧复核；"
                  "fall-02、03、08 边界各有 ±8 帧不确定度。卧地窗口由脚本对照视频选取。",
                  "", "|段号|视觉起始|前窗帧数|卧地区间（闭区间）|失衡前置信度|卧地置信度|卧地有人帧占比|",
                  "|---|---:|---:|---|---:|---:|---:|", *tails, "",
                  f"明确卧地的 {lying_frames} 帧中，{lying_empty} 帧完全漏检，"
                  f"{lying_weak} 帧的平均关键点置信度低于 0.3（含漏检）。", ""]
    lines += ["## Q2 总体检出率", "",
              f"{len(rows)} 段、{total:,} 帧中，{detected:,} 帧检出人（{detected/total:.2%}）。"
              f"帧加权平均检出人数 {avg_people:.3f}，关键点平均置信度 {avg_conf:.3f}；"
              f"低于 0.3 的帧有 {low:,} 帧（{low/total:.2%}），含零检测帧。逐段分母见附表。",
              "", "固定 yolov8n-pose.pt、imgsz=640、检测阈值 0.25。" + timing_text,
              "", "## Q3 整段丢失情况", "",
              f"连续至少 30 帧完全无人检出的区间共 {len(missing)} 个，涉及 {len(set(r[0] for r in missing))} 段。"]
    if missing:
        lines += ["", "|段号|起帧|末帧（含）|长度|", "|---|---:|---:|---:|"]
        lines += [f"|{seq}|{start}|{stop}|{stop-start+1}|" for seq, start, stop in missing]
    lines += ["", "## Q4 多人帧分布", "",
              f"全量共有 {multiple:,} 帧检出至少两人（{multiple/total:.2%}）。按占比降序、同率按编号排序。", "",
              "|段号|多人帧|总帧数|占比|", "|---|---:|---:|---:|"]
    for seq, n, _, _, _, _, multi in sorted(detail, key=lambda r: (-r[6]/r[1], r[0]))[:5]:
        lines.append(f"|{seq}|{multi}|{n}|{multi/n:.2%}|")
    lines += ["", "## 对 A3 的影响与建议阈值", "",
              "- 沿用题定 0.3 作为姿态质量门槛。低质量帧从姿态特征计算中剔除，保留原始时间轴和缺失标记。",
              "- 连续无人达到 30 帧时暂停静止确认，只报疑似。若人仍可见，仍需检查人体框、关键点覆盖与目标身份。",
              "- 多人帧按目标连续性关联，同一槽的相邻帧可能属于不同人。置信度与检出率均不能替代跌倒准确率。",
              "- 本次仅评估 cam0 RGB 的剪辑。真实独居老人住宅、无光、其他机位以及每户每天误报率均无本次实测依据。",
              "", "数据来源为 University of Rzeszów 的 UR Fall Detection Dataset，"
              "项目记录许可为 CC BY-NC-SA 4.0，本次用于非商业学术研究。",
              "", "## 附：逐段明细表（70 行）", "",
              "|段号|帧数|平均人数|平均关键点置信度|有人帧占比|低于 0.3|多人帧占比|",
              "|---|---:|---:|---:|---:|---:|---:|"]
    for seq, n, ppl, conf, seen, weak, multi in detail:
        lines.append(f"|{seq}|{n}|{ppl:.3f}|{conf:.3f}|{seen/n:.2%}|{weak/n:.2%}|{multi/n:.2%}|")
    output = ALGO / "reports/keypoint_quality.md"
    with staged_output(output) as tmp:
        tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(conclusion)


if __name__ == "__main__":
    main()
