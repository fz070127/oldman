"""Per-person geometry from A2 detections, with explicit missing values."""

from __future__ import annotations

from dataclasses import dataclass
from math import atan2, degrees, hypot, isfinite


@dataclass(frozen=True)
class Box:
    left: float
    top: float
    right: float
    bottom: float

    @classmethod
    def from_xyxy(cls, coords):
        box = cls(*map(float, coords))
        if not all(map(isfinite, (box.left, box.top, box.right, box.bottom))):
            return None
        return box if box.width > 0 and box.height > 0 else None

    @property
    def width(self):
        return self.right - self.left

    @property
    def height(self):
        return self.bottom - self.top

    @property
    def center(self):
        return (self.left + self.right) / 2, (self.top + self.bottom) / 2

    @property
    def diagonal(self):
        return hypot(self.width, self.height)

    def iou(self, other):
        overlap_w = max(0.0, min(self.right, other.right) - max(self.left, other.left))
        overlap_h = max(0.0, min(self.bottom, other.bottom) - max(self.top, other.top))
        intersection = overlap_w * overlap_h
        union = self.width * self.height + other.width * other.height - intersection
        return intersection / union


@dataclass(frozen=True)
class Features:
    torso_angle: float | None
    body_height: float | None
    aspect_ratio: float | None
    v_drop: float | None
    kp_conf: float | None
    motion: float | None
    bbox_conf: float | None


def torso_angle(keypoints, scores, point_conf_min):
    joints = (5, 6, 11, 12)
    if keypoints is None or scores is None or any(scores[i] < point_conf_min for i in joints):
        return None
    left_shoulder, right_shoulder, left_hip, right_hip = (keypoints[i] for i in joints)
    dx, dy = ((float(left_hip[i]) + float(right_hip[i])
               - float(left_shoulder[i]) - float(right_shoulder[i])) / 2 for i in range(2))
    if not (isfinite(dx) and isfinite(dy)) or (dx == 0 and dy == 0):
        return None
    return degrees(atan2(abs(dy), abs(dx)))


def center_motion(boxes):
    """Maximum displacement from the first observed center, in its box diagonals."""
    if len(boxes) < 2:
        return None
    first = boxes[0]
    x, y = first.center
    return max(hypot(cx - x, cy - y) for cx, cy in (box.center for box in boxes[1:])) / first.diagonal


def extract_features(box, keypoints, point_scores, box_score, *, frame_height,
                     point_conf_min, previous_box=None, elapsed_sec=None, recent_boxes=()):
    # The box does not encode hip_y. Use its vertical extent as the box-only proxy.
    height = box.height / frame_height if box else None
    v_drop = None
    if box and previous_box and elapsed_sec and elapsed_sec > 0:
        v_drop = (previous_box.height - box.height) / frame_height / elapsed_sec
    kp_conf = None if point_scores is None else float(sum(map(float, point_scores)) / len(point_scores))
    return Features(
        torso_angle=torso_angle(keypoints, point_scores, point_conf_min),
        body_height=height,
        aspect_ratio=box.width / box.height if box else None,
        v_drop=v_drop,
        kp_conf=kp_conf,
        motion=center_motion([*recent_boxes, box]) if box else None,
        bbox_conf=float(box_score) if box and box_score is not None else None,
    )
