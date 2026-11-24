"""C1: 在同一 70 段 UR Fall 数据上横评三个姿态模型。

指标全部来自实际落盘的 npz / 计时文件 / 权重，不写估计值：
- 17 点平均置信度、肩髋四点置信度、低置信帧率、有人帧率、多人帧率
- 全量提取的端到端 ms/帧、模型参数量
- val 上的「不重训直接迁移」诊断（同一冻结 ST-GCN 权重 + 同一阈值）

选型规则按实测结果给出，不预先写死提升幅度。若建议更换姿态模型，
报告必须同时说明需要重跑 B3/B4/B6/C2，不能拿旧分数冒充升级结果。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

from ur_manifest import ALGO, read_manifest, staged_output

if str(ALGO) not in sys.path:
    sys.path.insert(0, str(ALGO))

from extract_keypoints import configure, validate  # noqa: E402

C1 = ALGO / "data/processed/c1"
OUT_JSON = C1 / "pose_compare.json"
OUT_MD = ALGO / "reports/c1_pose_comparison.md"
B6_THRESHOLD = 0.0191
SHOULDER_HIP = (5, 6, 11, 12)
LOW_CONF = 0.3

MODELS = (
    ("yolov8n-pose", "yolov8n-pose.pt", ALGO / "data/processed/keypoints",
     ALGO / "data/processed/extraction_time.json"),
    ("yolov8s-pose", "yolov8s-pose.pt", C1 / "yolov8s/keypoints",
     C1 / "yolov8s/extraction_time.json"),
    ("yolo11n-pose", "yolo11n-pose.pt", C1 / "yolo11n/keypoints",
     C1 / "yolo11n/extraction_time.json"),
)


def val_members():
    with (ALGO / "data/splits/val.csv").open(encoding="utf-8-sig", newline="") as f:
        return [r["seq_id"] for r in csv.DictReader(f)]


def accumulate(stats, seq_id, n_people, conf):
    mean_all = conf.mean(axis=1)
    mean_sh = conf[:, list(SHOULDER_HIP)].mean(axis=1)
    entry = {
        "frames": int(len(mean_all)),
        "conf_sum": float(mean_all.sum()),
        "sh_sum": float(mean_sh.sum()),
        "low_conf_frames": int((mean_all < LOW_CONF).sum()),
        "person_frames": int((n_people > 0).sum()),
        "multi_person_frames": int((n_people >= 2).sum()),
    }
    stats["all"]["sequences"].append(seq_id)
    for key in ("frames", "conf_sum", "sh_sum", "low_conf_frames",
                "person_frames", "multi_person_frames"):
        stats["all"][key] += entry[key]
    if seq_id in stats["val_ids"]:
        stats["val"]["sequences"].append(seq_id)
        for key in ("frames", "conf_sum", "sh_sum", "low_conf_frames",
                    "person_frames", "multi_person_frames"):
            stats["val"][key] += entry[key]
    return entry


def finalize(bucket):
    f = bucket["frames"]
    if not f:
        return None
    return {
        "frames": f,
        "sequences": len(bucket["sequences"]),
        "mean_keypoint_confidence": round(bucket["conf_sum"] / f, 5),
        "shoulder_hip_four_point_confidence": round(bucket["sh_sum"] / f, 5),
        "low_confidence_frame_rate": round(bucket["low_conf_frames"] / f, 5),
        "person_detection_rate": round(bucket["person_frames"] / f, 5),
        "multi_person_frame_rate": round(bucket["multi_person_frames"] / f, 5),
    }


def empty_bucket(val_ids):
    # all 与 val 必须是独立字典与独立列表，否则共享 sequences 引用会重复计数。
    def new():
        return {"frames": 0, "conf_sum": 0.0, "sh_sum": 0.0,
                "low_conf_frames": 0, "person_frames": 0,
                "multi_person_frames": 0, "sequences": []}
    return {"all": new(), "val": new(), "val_ids": set(val_ids)}


def model_metrics(name, weights_name, kp_dir, timing_path, manifest, val_ids):
    weights = ALGO / "data/processed/weights" / weights_name
    configure(kp_dir, weights, weights_name)
    stats = empty_bucket(val_ids)
    per_sequence = {}
    for seq_id, row in manifest.items():
        path = kp_dir / f"{seq_id}.npz"
        n = int(row["frame_count"])
        validate(path, seq_id, n)  # 复用 A2 的完整产物校验，含 meta.model 匹配
        with np.load(path, allow_pickle=False) as archive:
            n_people = archive["n_people"]
            conf = archive["kpts_conf"][:, 0].astype(np.float64)
        per_sequence[seq_id] = accumulate(stats, seq_id, n_people, conf)
    timing = None
    if timing_path.exists():
        data = json.loads(timing_path.read_text(encoding="utf-8"))
        if (data.get("frames"), data.get("sequences")) == (stats["all"]["frames"], 70):
            timing = {"ms_per_frame": round(float(data["ms_per_frame"]), 3),
                      "wall_sec": round(float(data["wall_sec"]), 2),
                      "workers": data["workers"]}
    parameters = None
    try:
        import torch
        from ultralytics import YOLO
        model = YOLO(str(weights), task="pose").model
        parameters = int(sum(p.numel() for p in model.parameters()))
    except Exception as error:  # 诊断项，失败不影响主指标
        parameters = f"n/a ({type(error).__name__})"
    return {
        "name": name,
        "weights": weights_name,
        "keypoints_dir": str(kp_dir),
        "sha256": hashlib.sha256(weights.read_bytes()).hexdigest(),
        "all": finalize(stats["all"]),
        "val": finalize(stats["val"]),
        "timing": timing,
        "parameters": parameters,
    }


def transfer_diagnosis(name):
    """同一冻结 ST-GCN 权重、同一阈值，在 val 上的不重训直接迁移表现。"""
    # name 形如 yolov8n-pose，而分数目录为去掉 -pose 的 yolov8n。
    short = name[:-5] if name.endswith("-pose") else name
    path = C1 / short / "scores_val.json"
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    fall_hits, adl_hits, maxes = [], [], []
    for seq in payload["sequences"]:
        peak = max(seq["scores"]) if seq["scores"] else 0.0
        maxes.append(peak)
        if peak >= B6_THRESHOLD:
            (fall_hits if seq["label"] == "fall" else adl_hits).append(seq["seq_id"])
    return {
        "threshold": B6_THRESHOLD,
        "val_fall_detected": len(fall_hits),
        "val_fall_total": sum(1 for s in payload["sequences"] if s["label"] == "fall"),
        "val_adl_false_alarms": len(adl_hits),
        "val_adl_total": sum(1 for s in payload["sequences"] if s["label"] != "fall"),
        "mean_sequence_peak_prob": round(float(np.mean(maxes)), 6),
        "note": ("未重训 ST-GCN，仅用于观察姿态模型更换后的分布偏移；"
                 "不能作为升级后的正式检测指标，也不能写入 C3 对比表"),
    }


def decide(rows):
    base = rows[0]
    base_diag = base.get("transfer_diagnosis") or {}
    candidates = []
    for row in rows[1:]:
        d_conf = row["all"]["mean_keypoint_confidence"] - base["all"]["mean_keypoint_confidence"]
        d_sh = (row["all"]["shoulder_hip_four_point_confidence"]
                - base["all"]["shoulder_hip_four_point_confidence"])
        d_low = (base["all"]["low_confidence_frame_rate"]
                 - row["all"]["low_confidence_frame_rate"])
        speed = None
        if row["timing"] and base["timing"]:
            speed = round(row["timing"]["ms_per_frame"] / base["timing"]["ms_per_frame"], 3)
        diag = row.get("transfer_diagnosis")
        diag_ok = bool(diag
                       and diag["val_fall_detected"] >= base_diag.get("val_fall_detected", 0)
                       and diag["val_adl_false_alarms"] <= base_diag.get("val_adl_false_alarms", 999))
        qualifies = d_conf >= 0.01 and d_sh >= 0.01 and d_low >= 0.01 and diag_ok
        candidates.append({
            "name": row["name"], "delta_mean_conf": round(d_conf, 5),
            "delta_shoulder_hip_conf": round(d_sh, 5),
            "delta_low_conf_rate_reduction": round(d_low, 5),
            "speed_ratio_vs_baseline": speed,
            "transfer_not_worse": diag_ok,
            "qualifies_for_upgrade": qualifies,
        })
    chosen = next((c["name"] for c in candidates if c["qualifies_for_upgrade"]), base["name"])
    return {
        "rule": ("候选需在 17 点均值、肩髋四点均值上各提升 ≥0.01，低置信帧率下降 ≥0.01，"
                 "且 val 不重训迁移诊断不劣于 baseline；否则保留 baseline"),
        "candidates": candidates,
        "selected": chosen,
        "baseline": base["name"],
        "upgraded": chosen != base["name"],
        "if_upgraded": ("必须重跑 B3 窗口构建、B4 训练、B6 对比与 C2 调参后，"
                        "才能更新 C3 升级前后对比表"),
    }


def write_markdown(report):
    rows = report["models"]
    lines = [
        "# C1 · 姿态模型横评",
        "",
        f"- 数据：UR Fall 70 段、{sum(int(r['frame_count']) for r in report['manifest'].values()):,} 帧 cam0 RGB。",
        "- 三个模型均使用 imgsz=640、conf=0.25，提取两个人体槽位，指标取最高分槽（slot 0）。",
        "- 低置信帧定义为 17 点平均置信度 < 0.3，含完全漏检帧。",
        "",
        "## 全量关键点质量与速度",
        "",
        "| 模型 | 17点均值 | 肩髋四点 | 低置信帧率 | 有人帧率 | 多人帧率 | ms/帧 | 参数量 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        a = r["all"]
        ms = r["timing"]["ms_per_frame"] if r["timing"] else "n/a"
        lines.append(
            f"| {r['name']} | {a['mean_keypoint_confidence']:.4f} | "
            f"{a['shoulder_hip_four_point_confidence']:.4f} | "
            f"{a['low_confidence_frame_rate']:.2%} | {a['person_detection_rate']:.2%} | "
            f"{a['multi_person_frame_rate']:.2%} | {ms} | {r['parameters']} |")
    lines += ["", "## val 划分上的同样指标", "",
              "| 模型 | 17点均值 | 肩髋四点 | 低置信帧率 | 有人帧率 |",
              "|---|---:|---:|---:|---:|"]
    for r in rows:
        v = r["val"]
        lines.append(f"| {r['name']} | {v['mean_keypoint_confidence']:.4f} | "
                     f"{v['shoulder_hip_four_point_confidence']:.4f} | "
                     f"{v['low_confidence_frame_rate']:.2%} | {v['person_detection_rate']:.2%} |")
    lines += ["", "## 不重训直接迁移诊断（val，仅作观察）", "",
              "同一冻结 ST-GCN 权重、同一阈值 0.0191，只用不同姿态模型的关键点重建稠密窗口。",
              "此表说明分布偏移，不是升级后的检测性能结论。", "",
              "| 模型 | 跌倒检出 | ADL 误报 | 段峰值概率均值 |", "|---|---:|---:|---:|"]
    for r in rows:
        d = r.get("transfer_diagnosis")
        if not d:
            lines.append(f"| {r['name']} | n/a | n/a | n/a |")
        else:
            lines.append(f"| {r['name']} | {d['val_fall_detected']}/{d['val_fall_total']} | "
                         f"{d['val_adl_false_alarms']}/{d['val_adl_total']} | "
                         f"{d['mean_sequence_peak_prob']:.6f} |")
    d = report["decision"]
    lines += ["", "## 选型结论", "", f"- 判定规则：{d['rule']}", "",
              "| 候选 | 17点均值增量 | 肩髋四点增量 | 低置信帧率下降 | 速度倍率 | 迁移不劣于 | 符合升级 |",
              "|---|---:|---:|---:|---:|---|---|"]
    for c in d["candidates"]:
        def f(v):
            return "n/a" if v is None else f"{v:+.4f}" if isinstance(v, float) else str(v)
        lines.append(f"| {c['name']} | {f(c['delta_mean_conf'])} | "
                     f"{f(c['delta_shoulder_hip_conf'])} | "
                     f"{f(c['delta_low_conf_rate_reduction'])} | "
                     f"{f(c['speed_ratio_vs_baseline'])} | "
                     f"{'是' if c['transfer_not_worse'] else '否'} | "
                     f"{'是' if c['qualifies_for_upgrade'] else '否'} |")
    lines += ["", f"**最终选择：{d['selected']}**（baseline 为 {d['baseline']}）。", ""]
    if d["upgraded"]:
        lines.append(f"注意：{d['if_upgraded']}。本次尚未重跑，因此 C3 表不得使用新模型分数。")
    else:
        lines.append("候选未同时满足质量增益与迁移稳定性条件，保留 baseline；"
                     "因此 B 阶段冻结窗口、ST-GCN 权重与 C2 分数全部保持有效，无需重训。")
    lines += ["", "## 权重指纹", ""]
    for r in rows:
        lines.append(f"- `{r['weights']}` SHA256 `{r['sha256']}`")
    lines += ["", "数据来源为 University of Rzeszów 的 UR Fall Detection Dataset，"
              "项目记录许可为 CC BY-NC-SA 4.0，本次用于非商业学术研究。", ""]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-json", type=Path, default=OUT_JSON)
    parser.add_argument("--output-md", type=Path, default=OUT_MD)
    args = parser.parse_args()
    manifest = read_manifest()
    val_ids = val_members()
    rows = []
    for name, weights, kp_dir, timing in MODELS:
        row = model_metrics(name, weights, kp_dir, timing, manifest, val_ids)
        row["transfer_diagnosis"] = transfer_diagnosis(name)
        rows.append(row)
        print(json.dumps({"model": name, "all": row["all"],
                          "timing": row["timing"],
                          "transfer": row["transfer_diagnosis"]}, ensure_ascii=False))
    report = {
        "models": rows,
        "decision": decide(rows),
        "manifest": {k: {"frame_count": v["frame_count"]} for k, v in manifest.items()},
    }
    with staged_output(args.output_json) as tmp:
        tmp.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with staged_output(args.output_md) as tmp:
        tmp.write_text(write_markdown(report), encoding="utf-8")
    print(json.dumps({"selected": report["decision"]["selected"],
                      "upgraded": report["decision"]["upgraded"],
                      "output": str(args.output_md)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
