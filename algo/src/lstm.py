"""B4 对照模型：骨架 LSTM。

路线要求 ST-GCN 为主干、骨架 LSTM 仅作对照，因此这里刻意不做图卷积：
每帧把 17 个关节的 (x, y, conf | vx, vy, ax, ay) 展平成 119 维向量，
送入两层 LSTM，取末时刻隐状态做二分类。输入窗口、归一化、标签、
训练超参与 ST-GCN 完全一致，保证对比公平。
"""

from __future__ import annotations

import torch
import torch.nn as nn

NUM_JOINTS = 17
JOINT_CHANNELS = 3
MOTION_CHANNELS = 4
FEATURES = NUM_JOINTS * (JOINT_CHANNELS + MOTION_CHANNELS)  # 119


class SkeletonLSTM(nn.Module):
    def __init__(self, hidden: int = 64, layers: int = 2, dropout: float = 0.5):
        super().__init__()
        self.lstm = nn.LSTM(
            FEATURES, hidden, num_layers=layers, batch_first=True,
            dropout=dropout if layers > 1 else 0.0,
        )
        self.head = nn.Sequential(
            nn.Linear(hidden, 32), nn.ReLU(), nn.Dropout(dropout), nn.Linear(32, 1))

    def forward(self, joint: torch.Tensor, motion: torch.Tensor) -> torch.Tensor:
        # joint (N,3,T,V) / motion (N,4,T,V) -> (N,T,V,7) -> (N,T,119)
        frames = torch.cat([joint.permute(0, 2, 3, 1), motion.permute(0, 2, 3, 1)],
                           dim=-1)
        out, _ = self.lstm(frames.flatten(2))
        return self.head(out[:, -1]).reshape(-1)

    def parameter_count(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)
