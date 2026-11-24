"""Optional ST-GCN confirmation stage for the edge fall agent.

Implements the B5/B6 fusion conclusion on the live stream:
- the dual-stream ST-GCN scores a sliding 30-frame keypoint window;
- a window at or above the threshold triggers a candidate P1;
- a rule event (evidence frame) within CONFIRM_RADIUS frames upgrades it to P0.
- rule-only P1 events are also re-scored; a confirmed window upgrades them.

C2 adds an optional multi-window consensus on the model-led path only: window
scores are sampled every `score_stride_frames` frames and a moving average of
`window` consecutive scores must reach `threshold`. This mirrors the offline
`tune_consensus.py` evaluation; the rule-gated P0 upgrade path is unchanged.

The buffer stores the top-confidence person per frame (slot-0 semantics,
matching how the model was trained and evaluated offline).
"""
import logging
from collections import deque
from pathlib import Path

ALGO = Path(__file__).resolve().parents[1] / "algo"
import sys

sys.path.insert(0, str(ALGO))
import numpy as np

from src.consensus import moving_average_consensus
from src.window_utils import make_window

LOG = logging.getLogger(__name__)
WINDOW = 30
CONFIRM_RADIUS = 45  # frames (streaming, ~1.5 s at 30 fps)


def _geometry_signals(kpts, conf):
    """Approximate the A3 signal set from raw keypoints for model events."""
    shoulder_mid = kpts[5:7].mean(axis=0)
    hip_mid = kpts[11:13].mean(axis=0)
    torso = hip_mid - shoulder_mid
    torso_angle = float(np.degrees(np.arctan2(abs(torso[0]), abs(torso[1] + 1e-6))))
    all_pts = kpts[conf > 0.3]
    if len(all_pts) >= 2:
        w = float(all_pts[:, 0].max() - all_pts[:, 0].min())
        h = float(all_pts[:, 1].max() - all_pts[:, 1].min())
        aspect = w / (h + 1e-6)
    else:
        aspect = 1.0
    return {"torso_angle": torso_angle, "height_drop": 0.0,
            "aspect_ratio": aspect, "kp_conf": float(conf.mean())}


class StgcnConfirm:
    def __init__(self, weights, threshold, device="cpu", consensus=None):
        import torch
        from src.stgcn import DualStreamSTGCN

        if not Path(weights).is_file():
            raise FileNotFoundError(f"Missing ST-GCN weights: {weights}")
        ckpt = torch.load(weights, map_location=device, weights_only=True)
        args = ckpt.get("args", {})
        hidden = tuple(args.get("hidden") or (64, 64, 128))
        dropout = float(args.get("dropout") or 0.3)
        self.model = DualStreamSTGCN(hidden=hidden, dropout=dropout).to(device)
        self.model.load_state_dict(ckpt["model_state"])
        self.model.eval()
        self.device = torch.device(device)
        self.threshold = float(threshold)
        self.buf = deque(maxlen=WINDOW)  # (kpts(17,2), conf(17,)) slot 0
        self.last_rule_frame = None
        self.last_alert_frame = None
        self.last_alert_prob = 0.0

        # C2 可选共识：None 时完全退回 B6 的单窗越阈行为。
        self.consensus = dict(consensus or {})
        self.consensus_window = int(self.consensus.get("window", 0))
        self.consensus_threshold = float(
            self.consensus.get("threshold", self.threshold))
        self.consensus_stride = max(1, int(
            self.consensus.get("score_stride_frames", 1)))
        self.scores = (deque(maxlen=self.consensus_window)
                       if self.consensus_window > 0 else None)
        self.last_scored_frame = None
        self.last_pose_frame = None

    def feed_pose(self, frame, pose):
        """Buffer the top-confidence person's keypoints for this frame.

        Frames with no detection append zeros with zero confidence — the same
        convention as the offline keypoints store, so make_window masks them
        instead of invalidating the window (matches B6 frozen semantics).
        """
        if self.last_pose_frame is not None and frame != self.last_pose_frame + 1:
            self.buf.clear()
            if self.scores is not None:
                self.scores.clear()
            self.last_scored_frame = None
        self.last_pose_frame = frame
        _, kpts, confs, scores, n = pose
        if n == 0:
            self.buf.append((np.zeros((17, 2)), np.zeros(17)))
            return
        best = int(np.argmax(scores))
        self.buf.append((kpts[best], confs[best]))

    def window_prob(self):
        if len(self.buf) < WINDOW:
            return None
        kpts = np.stack([f[0] for f in self.buf])
        conf = np.stack([f[1] for f in self.buf])
        built = make_window(kpts, conf, 0, WINDOW)
        if built is None:
            return None
        joint, motion, _scale = built
        import torch
        with torch.no_grad():
            j = torch.from_numpy(joint[None]).to(self.device)
            m = torch.from_numpy(motion[None]).to(self.device)
            prob = float(torch.sigmoid(self.model(j, m)).reshape(-1)[0])
        return prob

    def rule_evidence(self, engine_frame):
        self.last_rule_frame = engine_frame

    def recent_model_alert(self, engine_frame):
        """Peak model probability from an alert within the confirm radius,
        or None when the model has not fired recently."""
        if self.last_alert_frame is None or abs(engine_frame - self.last_alert_frame) > CONFIRM_RADIUS:
            return None
        return self.last_alert_prob

    def confirm_rule_event(self):
        """Re-score the current window for a rule P1 (route B5 upgrade)."""
        prob = self.window_prob()
        return prob if prob is not None and prob >= self.threshold else None

    def _consensus_prob(self, engine_frame):
        """按冻结配置采样窗口分数并做移动平均共识；未启用时退回单窗越阈。"""
        if self.scores is None:
            prob = self.window_prob()
            return prob if prob is not None and prob >= self.threshold else None
        if (self.last_scored_frame is not None
                and engine_frame - self.last_scored_frame < self.consensus_stride):
            return None
        prob = self.window_prob()
        self.last_scored_frame = engine_frame
        if prob is None:
            self.scores.clear()
            return None
        self.scores.append(prob)
        result = moving_average_consensus(
            self.scores, self.consensus_threshold, self.consensus_window)
        if not result.triggered:
            return None
        return sum(self.scores) / len(self.scores)

    def model_event(self, engine_frame, *, allow_alert=True):
        """Model-led candidate; returns (level, prob, signals) or None."""
        if len(self.buf) < WINDOW:
            return None
        if self.last_alert_frame is not None and engine_frame - self.last_alert_frame < CONFIRM_RADIUS:
            allow_alert = False
        if not allow_alert and self.scores is None:
            return None
        prob = self._consensus_prob(engine_frame)
        if prob is None or not allow_alert:
            return None
        last = self.buf[-1]
        kpts, conf = last
        rule_near = (self.last_rule_frame is not None
                     and abs(engine_frame - self.last_rule_frame) <= CONFIRM_RADIUS)
        level = "P0" if rule_near else "P1"
        self.last_alert_frame = engine_frame
        self.last_alert_prob = prob
        return level, prob, _geometry_signals(kpts, conf)
