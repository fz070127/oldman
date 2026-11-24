"""Shared window construction for the B-stage dual-stream ST-GCN.

Both the offline window builder and the fusion evaluator must turn a
sequence's slot-0 keypoints into identical (joint, motion) tensors, so the
logic lives here once. Coordinates are hip-center translated and divided by
the window's median torso length; invalid joints are zeroed and flagged via
the confidence channel.
"""

from __future__ import annotations

import numpy as np

COCO_EDGES = (
    (0, 1), (0, 2), (1, 3), (2, 4),
    (0, 5), (0, 6), (5, 7), (7, 9), (6, 8), (8, 10),
    (5, 11), (6, 12), (11, 13), (13, 15), (12, 14), (14, 16),
    (5, 6), (11, 12),
)

# COCO joint indices.
L_SHOULDER, R_SHOULDER = 5, 6
L_HIP, R_HIP = 11, 12

JOINT_CHANNELS = 3   # x, y, conf
MOTION_CHANNELS = 4  # vx, vy, ax, ay


def build_adjacency():
    """Normalized (I + A) with symmetric degree scaling, fixed topology."""
    n = 17
    adj = np.zeros((n, n), dtype=np.float32)
    for i, j in COCO_EDGES:
        adj[i, j] = 1.0
        adj[j, i] = 1.0
    adj += np.eye(n, dtype=np.float32)
    deg = adj.sum(axis=1)
    d_inv_sqrt = 1.0 / np.sqrt(np.maximum(deg, 1e-12))
    return adj * d_inv_sqrt[:, None] * d_inv_sqrt[None, :]


def _pair_midpoint(kpts, conf, i, j, conf_min):
    """Midpoint of joints i and j; valid only when both joints are reliable."""
    if conf[i] >= conf_min and conf[j] >= conf_min:
        return (kpts[i] + kpts[j]) / 2.0, True
    return np.zeros(2, dtype=np.float32), False


def load_slot0(npz_path):
    """Return (kpts, conf, n_people) for the primary slot of a sequence."""
    with np.load(npz_path, allow_pickle=False) as archive:
        kpts = archive["kpts"][:, 0].astype(np.float32)       # (N,17,2)
        conf = archive["kpts_conf"][:, 0].astype(np.float32)   # (N,17)
        people = archive["n_people"].astype(np.int64)          # (N,)
    return kpts, conf, people


def make_window(kpts, conf, start, length, conf_min=0.30):
    """Build normalized joint/motion tensors for frames [start, start+length).

    Root translation uses the hip midpoint when available, otherwise the
    shoulder midpoint; frames with neither keep the raw (pixel) coordinates
    subtracted by zero, i.e. they are only scaled. The window scale is the
    median over frames where both midpoints exist. Returns
    (joint (3,T,V), motion (4,T,V), scale) or None when unusable.
    """
    k = kpts[start:start + length]   # (T,17,2)
    c = conf[start:start + length]    # (T,17)
    t = k.shape[0]
    if t == 0:
        return None
    valid = c >= conf_min             # (T,17)

    hip_mid = np.zeros((t, 2), dtype=np.float32)
    shoulder_mid = np.zeros((t, 2), dtype=np.float32)
    hip_ok = np.zeros(t, dtype=bool)
    shoulder_ok = np.zeros(t, dtype=bool)
    for f in range(t):
        hip_mid[f], hip_ok[f] = _pair_midpoint(k[f], c[f], L_HIP, R_HIP, conf_min)
        shoulder_mid[f], shoulder_ok[f] = _pair_midpoint(
            k[f], c[f], L_SHOULDER, R_SHOULDER, conf_min)

    torso = np.linalg.norm(hip_mid - shoulder_mid, axis=-1)
    both_ok = hip_ok & shoulder_ok
    if both_ok.any():
        scale = float(np.median(torso[both_ok]))
    else:
        return None
    if not np.isfinite(scale) or scale <= 1e-6:
        return None

    root = np.where(hip_ok[:, None], hip_mid,
                   np.where(shoulder_ok[:, None], shoulder_mid, 0.0))

    norm = (k - root[:, None, :]) / scale       # (T,17,2)
    norm = norm * valid[..., None]              # zero invalid coordinates

    vel = np.zeros_like(norm)
    if t > 1:
        vel[1:] = norm[1:] - norm[:-1]
    acc = np.zeros_like(norm)
    if t > 2:
        acc[2:] = vel[2:] - vel[1:-1]

    joint = np.concatenate(
        [norm.transpose(2, 0, 1), (c * valid)[:, :, None].transpose(2, 0, 1)], axis=0)
    motion = np.concatenate([vel.transpose(2, 0, 1), acc.transpose(2, 0, 1)], axis=0)
    return joint.astype(np.float32), motion.astype(np.float32), scale
