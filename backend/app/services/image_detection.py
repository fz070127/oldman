"""单帧图片的人体状态判断。

姿态关键点由 YOLOv8n-pose ONNX 提取；状态模型使用 UR Fall Detection 数据集
训练得到的双流 ST-GCN ONNX 权重。单帧没有时间序列，因此这里输出的是姿态风险
判断，跌倒确认仍需多帧序列共识。
"""

from __future__ import annotations

import io
import math
import os
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

DEFAULT_MODELS = Path(__file__).resolve().parents[3] / "algo/data/processed/onnx"
MAX_IMAGE_BYTES = 12 * 1024 * 1024
INPUT_SIZE = 640
CONF_MIN = 0.25
POINT_CONF_MIN = 0.30
WINDOW = 30
# 由 UR Fall Detection 的 18 个真实帧标定得出（tools/calibrate_image_detection.py）：
# 跌倒躺卧帧宽高比 2.05～2.51、归一化身高 0.21～0.32、躯干角 15～26 度；
# 日常活动帧宽高比 0.33～0.81。单帧 ST-GCN 分数两类重叠，仅作参考。
LYING_ASPECT = float(os.environ.get("IMAGE_LYING_ASPECT", "1.40"))
LYING_HEIGHT = float(os.environ.get("IMAGE_LYING_HEIGHT", "0.55"))
LYING_ANGLE = float(os.environ.get("IMAGE_LYING_ANGLE", "45.0"))
SUSPECT_ASPECT = float(os.environ.get("IMAGE_SUSPECT_ASPECT", "1.15"))


@lru_cache(maxsize=2)
def _open_session(path: Path):
    import onnxruntime as ort

    return ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])


def _pose_session():
    path = Path(os.environ.get("POSE_ONNX_PATH", DEFAULT_MODELS / "yolov8n-pose.onnx"))
    if not path.is_file():
        raise FileNotFoundError(path)
    return _open_session(path)


def _stgcn_session():
    path = Path(os.environ.get("STGCN_ONNX_PATH", DEFAULT_MODELS / "stgcn_static.onnx"))
    return _open_session(path) if path.is_file() else None


def _letterbox(image: Image.Image) -> tuple[np.ndarray, float, float, float]:
    width, height = image.size
    gain = min(INPUT_SIZE / width, INPUT_SIZE / height)
    resized = image.resize(
        (max(1, round(width * gain)), max(1, round(height * gain))), Image.Resampling.BILINEAR
    )
    pad_x = (INPUT_SIZE - resized.width) // 2
    pad_y = (INPUT_SIZE - resized.height) // 2
    canvas = Image.new("RGB", (INPUT_SIZE, INPUT_SIZE), (114, 114, 114))
    canvas.paste(resized, (pad_x, pad_y))
    array = np.asarray(canvas, dtype=np.float32) / 255.0
    return array.transpose(2, 0, 1)[None, ...], gain, pad_x, pad_y


def _decode(output: np.ndarray, gain: float, pad_x: float, pad_y: float):
    prediction = output[0].T
    # YOLOv8n-pose has a single implicit class: 4 box + 1 objectness + 17*3 keypoints.
    scores = np.where(np.isfinite(prediction).all(axis=1), prediction[:, 4], -np.inf)
    if not scores.size or scores.max() < CONF_MIN:
        return None
    best = int(np.argmax(scores))
    raw = prediction[best]
    cx, cy, bw, bh = raw[:4]
    left = (cx - bw / 2 - pad_x) / gain
    top = (cy - bh / 2 - pad_y) / gain
    right = (cx + bw / 2 - pad_x) / gain
    bottom = (cy + bh / 2 - pad_y) / gain
    points = raw[5:].reshape(17, 3).copy()
    points[:, 0] = (points[:, 0] - pad_x) / gain
    points[:, 1] = (points[:, 1] - pad_y) / gain
    return {
        "box": [round(float(v), 1) for v in (left, top, right, bottom)],
        "score": round(float(scores[best]), 4),
        "keypoints": [[round(float(x), 1), round(float(y), 1), round(float(c), 4)]
                      for x, y, c in points],
    }


def _torso_angle(points: np.ndarray, conf: np.ndarray) -> float | None:
    joints = (5, 6, 11, 12)
    if any(conf[i] < POINT_CONF_MIN for i in joints):
        return None
    shoulders = points[[5, 6]].mean(axis=0)
    hips = points[[11, 12]].mean(axis=0)
    dx, dy = hips - shoulders
    if math.hypot(dx, dy) < 1e-6:
        return None
    return round(math.degrees(math.atan2(abs(dy), abs(dx))), 1)


def _make_window(points: np.ndarray, conf: np.ndarray) -> tuple[np.ndarray, np.ndarray] | None:
    """Repeat one frame into a 30-frame window, matching the B-stage builder."""
    kpts = np.repeat(points[None, ...], WINDOW, axis=0)
    confs = np.repeat(conf[None, ...], WINDOW, axis=0)
    valid = confs >= POINT_CONF_MIN
    hip_ok = valid[:, 11] & valid[:, 12]
    shoulder_ok = valid[:, 5] & valid[:, 6]
    if not (hip_ok | shoulder_ok).any():
        return None
    hip_mid = kpts[:, [11, 12]].mean(axis=1)
    shoulder_mid = kpts[:, [5, 6]].mean(axis=1)
    torso = np.linalg.norm(hip_mid - shoulder_mid, axis=-1)
    usable = hip_ok & shoulder_ok
    if not usable.any():
        return None
    scale = float(np.median(torso[usable]))
    if not math.isfinite(scale) or scale <= 1e-6:
        return None
    root = np.where(hip_ok[:, None], hip_mid,
                    np.where(shoulder_ok[:, None], shoulder_mid, 0.0))
    norm = (kpts - root[:, None, :]) / scale * valid[..., None]
    velocity = np.zeros_like(norm)
    velocity[1:] = norm[1:] - norm[:-1]
    acceleration = np.zeros_like(norm)
    acceleration[2:] = velocity[2:] - velocity[1:-1]
    joint = np.concatenate(
        [norm.transpose(2, 0, 1), (confs * valid)[:, :, None].transpose(2, 0, 1)], axis=0
    ).astype(np.float32)
    motion = np.concatenate(
        [velocity.transpose(2, 0, 1), acceleration.transpose(2, 0, 1)], axis=0
    ).astype(np.float32)
    return joint[None, ...], motion[None, ...]


def _sigmoid(values: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(values, -30, 30)))


def detect_bytes(data: bytes) -> dict:
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise ValueError("图片不能为空且不能超过 12 MB")
    try:
        with Image.open(io.BytesIO(data), formats=("JPEG", "PNG", "WEBP")) as original:
            width, height = original.size
            if min(width, height) < 64 or max(width, height) > 6000:
                raise ValueError("图片尺寸须在 64～6000 像素之间")
            image = ImageOps.exif_transpose(original).convert("RGB")
    except (Image.DecompressionBombError, UnidentifiedImageError, OSError) as error:
        raise ValueError("无法识别的图片格式") from error
    width, height = image.size

    tensor, gain, pad_x, pad_y = _letterbox(image)
    pose = _decode(_pose_session().run(None, {"images": tensor})[0], gain, pad_x, pad_y)
    if pose is None:
        return {
            "status": "NO_PERSON",
            "label": "未检测到人",
            "score": 0.0,
            "modelScore": None,
            "geometry": None,
            "keypoints": [],
            "box": [],
            "imageSize": [width, height],
            "basis": "YOLOv8n-pose 未在当前画面检测到人体。",
        }

    points = np.array([[p[0], p[1]] for p in pose["keypoints"]], dtype=np.float32)
    conf = np.array([p[2] for p in pose["keypoints"]], dtype=np.float32)
    angle = _torso_angle(points, conf)
    left, top, right, bottom = pose["box"]
    aspect = round((right - left) / max(bottom - top, 1.0), 3)
    body_height = round((bottom - top) / height, 3)

    window = _make_window(points, conf)
    session = _stgcn_session() if window is not None else None
    model_score = None
    if session is not None and window is not None:
        logits = session.run(None, {"joint": window[0], "motion": window[1]})[0]
        model_score = round(float(_sigmoid(logits).reshape(-1)[0]), 4)

    lying_pose = (
        aspect > LYING_ASPECT
        and body_height < LYING_HEIGHT
        and (angle is None or angle < LYING_ANGLE)
    )
    suspect_pose = (
        aspect > SUSPECT_ASPECT
        and body_height < LYING_HEIGHT
        and (angle is None or angle < LYING_ANGLE + 10)
    )

    if lying_pose:
        status, label = "FALL", "疑似跌倒（躺卧姿态）"
        score = round(min(0.99, 0.70 + (aspect - LYING_ASPECT) * 0.10
                          + (LYING_HEIGHT - body_height) * 0.30), 4)
    elif suspect_pose:
        status, label = "SUSPECT", "姿态异常，请复核"
        score = round(min(0.75, 0.45 + (aspect - SUSPECT_ASPECT) * 0.15), 4)
    else:
        status, label = "NORMAL", "正常活动姿态"
        score = pose["score"]

    return {
        "status": status,
        "label": label,
        "score": score,
        "modelScore": model_score,
        "geometry": {
            "torsoAngle": angle,
            "aspectRatio": aspect,
            "bodyHeight": body_height,
            "lyingPose": bool(lying_pose),
        },
        "keypoints": pose["keypoints"],
        "box": pose["box"],
        "detectionScore": pose["score"],
        "imageSize": [width, height],
        "basis": (
            "判定规则由 UR Fall Detection 数据集真实帧标定（跌倒帧宽高比 2.05～2.51、"
            "日常活动 0.33～0.81）；关键点来自 YOLOv8n-pose，参考分为同数据集训练的"
            "双流 ST-GCN。单帧无时间序列，仅作姿态风险判断，跌倒确认需多帧共识。"
        ),
    }
