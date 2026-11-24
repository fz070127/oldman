"""按完整序列提取 UR Fall 的双槽位姿态数据。"""

import argparse
import hashlib
import json
import os
import time
import zipfile
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlretrieve

import cv2
import numpy as np

from ur_manifest import ALGO, indexed_frames, read_manifest, staged_output

DEFAULT_OUT = ALGO / "data/processed/keypoints"
DEFAULT_MODEL = "yolov8n-pose.pt"
DEFAULT_WEIGHTS = ALGO / "data/processed/weights" / DEFAULT_MODEL
DEFAULT_SHA256 = "c6fa93dd1ee4a2c18c900a45c1d864a1c6f7aba75d84f91648a30b7fb641d212"
OUT = DEFAULT_OUT
MODEL = DEFAULT_MODEL
WEIGHTS = DEFAULT_WEIGHTS
WEIGHTS_SHA256 = DEFAULT_SHA256
CONF = 0.25
SCHEMA = {
    "frames": ((), "int32"),
    "kpts": ((2, 17, 2), "float32"),
    "kpts_conf": ((2, 17), "float32"),
    "boxes": ((2, 4), "float32"),
    "scores": ((2,), "float32"),
    "n_people": ((), "int8"),
}
META = np.dtype([("seq_id", "U8"), ("model", "U32"), ("imgsz", "i4"),
                 ("conf_thres", "f4"), ("fps_assumed", "i4"), ("extracted_at", "U40")])
_pose = None


def configure(out, weights, model, sha256=None):
    global OUT, WEIGHTS, MODEL, WEIGHTS_SHA256, _pose
    OUT, WEIGHTS, MODEL = Path(out), Path(weights), model
    WEIGHTS_SHA256 = sha256
    _pose = None


def sequence_frames(row):
    paths = indexed_frames(ALGO / row["frame_dir"], row["seq_id"])
    if len(paths) != int(row["frame_count"]) or int(row["fps"]) != 30:
        raise ValueError(f"{row['seq_id']}: 帧数或帧率与总清单不符")
    return paths


def read_image(path):
    encoded = np.fromfile(path, np.uint8)
    try:
        image = cv2.imdecode(encoded, cv2.IMREAD_COLOR) if encoded.size else None
    except cv2.error as error:
        raise ValueError(f"图像解码失败: {path}") from error
    if image is None or image.shape != (480, 640, 3):
        raise ValueError(f"无法解码 640×480 RGB 帧: {path}")
    return image


def validate(path, seq, count):
    with np.load(path, allow_pickle=False) as archive:
        if set(archive.files) != set(SCHEMA) | {"meta"}:
            raise ValueError(f"{path}: 键不完整")
        a = {key: archive[key] for key in SCHEMA}
        for key, (tail, dtype) in SCHEMA.items():
            if a[key].shape != (count, *tail) or a[key].dtype != dtype:
                raise ValueError(f"{path}: {key} 形状或类型错误")
            if not np.isfinite(a[key]).all():
                raise ValueError(f"{path}: {key} 含非有限值")
        m = archive["meta"]
        if m.shape != () or m.dtype != META or (
            str(m["seq_id"]), str(m["model"]), int(m["imgsz"]),
            float(m["conf_thres"]), int(m["fps_assumed"])
        ) != (seq, MODEL, 640, CONF, 30):
            raise ValueError(f"{path}: 元数据错误")
        if datetime.fromisoformat(str(m["extracted_at"])).tzinfo is None:
            raise ValueError(f"{path}: 提取时间缺少时区")
        if not np.array_equal(a["frames"], np.arange(1, count + 1)) or (a["n_people"] < 0).any():
            raise ValueError(f"{path}: 帧号或人数错误")
        empty = np.arange(2)[None, :] >= a["n_people"][:, None]
        for key in ("scores", "kpts", "boxes", "kpts_conf"):
            if np.any(a[key][empty] != 0):
                raise ValueError(f"{path}: {key} 的空槽非零")
        for key in ("scores", "kpts_conf"):
            if np.any((a[key] < 0) | (a[key] > 1)):
                raise ValueError(f"{path}: {key} 超出置信度范围")
        if np.any(a["scores"][:, 1] > a["scores"][:, 0]) or (a["scores"][~empty] < CONF).any():
            raise ValueError(f"{path}: 检测分数或槽位顺序异常")


def extract(row):
    global _pose
    if _pose is None:
        os.environ.setdefault("YOLO_CONFIG_DIR", str(OUT.parent / "ultralytics"))
        import torch
        from ultralytics import YOLO
        torch.set_num_threads(4)
        cv2.setNumThreads(1)
        _pose = YOLO(str(WEIGHTS), task="pose")
    seq = row["seq_id"]
    paths = sequence_frames(row)
    n = len(paths)
    a = {key: np.zeros((n, *tail), dtype) for key, (tail, dtype) in SCHEMA.items()}
    a["frames"][:] = np.arange(1, n + 1)
    for start in range(0, n, 8):
        images = [read_image(p) for p in paths[start:start + 8]]
        results = _pose.predict(images, imgsz=640, conf=CONF, verbose=False)
        for offset, (_, result) in enumerate(zip(images, results, strict=True)):
            i = start + offset
            scores = result.boxes.conf.cpu().numpy()
            if len(scores) > 127:
                raise ValueError(f"{seq} 帧 {i+1}: 人数超出 int8 范围")
            a["n_people"][i] = len(scores)
            if len(scores):
                order = np.argsort(-scores, kind="stable")[:2]
                slots = slice(0, len(order))
                a["scores"][i, slots] = scores[order]
                a["boxes"][i, slots] = result.boxes.xyxy.cpu().numpy()[order]
                a["kpts"][i, slots] = result.keypoints.xy.cpu().numpy()[order]
                a["kpts_conf"][i, slots] = result.keypoints.conf.cpu().numpy()[order]
    meta = np.array((seq, MODEL, 640, CONF, 30, datetime.now(timezone.utc).isoformat()), dtype=META)
    with staged_output(OUT / f"{seq}.npz") as temp:
        np.savez_compressed(temp, **a, meta=meta)
        validate(temp, seq, n)
    print(f"{seq}: {n} frames", flush=True)
    return n


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--model", default=DEFAULT_MODEL, help="pose weights filename")
    parser.add_argument("--weights", type=Path, help="full path to pose weights")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="keypoints output dir")
    parser.add_argument("--sha256", help="expected sha256 for the weights file")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--resume", action="store_true")
    mode.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.workers < 1 or (args.limit is not None and args.limit < 1):
        parser.error("workers 和 limit 须为正整数")
    weights = args.weights or (ALGO / "data/processed/weights" / args.model)
    sha256 = args.sha256 or (DEFAULT_SHA256 if args.model == DEFAULT_MODEL else None)
    configure(args.out, weights, args.model, sha256)
    start = time.perf_counter()
    rows = list(read_manifest().values())[:args.limit]
    jobs = []
    for row in rows:
        seq = row["seq_id"]
        if args.verify or args.resume:
            paths = sequence_frames(row)
            try:
                validate(OUT / f"{seq}.npz", seq, len(paths))
            except (OSError, ValueError, EOFError, zipfile.BadZipFile) as error:
                if args.verify:
                    raise
                print(f"{seq}: 需提取 ({error})", flush=True)
            else:
                continue
        jobs.append(row)
    if args.verify:
        print(f"verified {len(rows)} sequences, {sum(int(r['frame_count']) for r in rows)} frames")
        return
    if not jobs:
        print(f"{len(rows)} sequences already verified")
        return
    if not WEIGHTS.exists():
        if args.model != DEFAULT_MODEL:
            raise FileNotFoundError(f"自定义权重需预先下载: {WEIGHTS}")
        url = "https://github.com/ultralytics/assets/releases/download/v8.3.0/" + MODEL
        WEIGHTS.parent.mkdir(parents=True, exist_ok=True)
        with staged_output(WEIGHTS) as tmp:
            urlretrieve(url, tmp)
            if hashlib.sha256(tmp.read_bytes()).hexdigest() != WEIGHTS_SHA256:
                raise ValueError(f"下载的模型校验失败: {url}")
    elif WEIGHTS_SHA256 and hashlib.sha256(WEIGHTS.read_bytes()).hexdigest() != WEIGHTS_SHA256:
        raise ValueError(f"模型文件校验失败: {WEIGHTS}")
    if args.workers == 1:
        count = sum(map(extract, jobs))
    else:
        with ProcessPoolExecutor(
            args.workers, initializer=configure, initargs=(OUT, WEIGHTS, MODEL, WEIGHTS_SHA256)
        ) as pool:
            count = sum(pool.map(extract, jobs))
    elapsed = time.perf_counter() - start
    timing = dict(sequences=len(jobs), frames=count, workers=args.workers,
                  wall_sec=elapsed, ms_per_frame=1000 * elapsed / count)
    print(json.dumps(timing), flush=True)
    if len(jobs) == len(read_manifest()):
        with staged_output(OUT.parent / "extraction_time.json") as tmp:
            tmp.write_text(json.dumps(timing, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
