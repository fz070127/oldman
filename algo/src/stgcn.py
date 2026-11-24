"""Dual-stream ST-GCN for fall-window confirmation (B4).

One stream consumes normalized joint coordinates plus keypoint confidence,
the other consumes velocity/acceleration derived from frame differences.
Each block keeps the fixed skeleton adjacency but multiplies it with a
learnable edge-importance mask, letting the model reweight graph edges.
"""

from __future__ import annotations

import numpy as np
import torch
import torch.nn as nn

from .window_utils import build_adjacency


class STGCNBlock(nn.Module):
    def __init__(self, cin, cout, kernel_temporal=5, adjacency=None, residual=True):
        super().__init__()
        self.register_buffer("A", torch.from_numpy(adjacency))
        self.edge = nn.Parameter(torch.ones(adjacency.shape))
        self.conv_channel = nn.Conv2d(cin, cout, kernel_size=1)
        self.tcn = nn.Conv2d(cout, cout, kernel_size=(kernel_temporal, 1),
                             padding=(kernel_temporal // 2, 0))
        self.bn = nn.BatchNorm2d(cout)
        self.relu = nn.ReLU(inplace=True)
        if not residual or cin != cout:
            self.downsample = nn.Conv2d(cin, cout, kernel_size=1) if cin != cout else None
            self.residual = cin == cout
        else:
            self.downsample = None
            self.residual = True

    def forward(self, x):                       # (N,C,T,V)
        a = self.A * self.edge                  # learnable-edge graph
        y = torch.einsum("vu,nctu->nctv", a, x)
        y = self.relu(self.bn(self.conv_channel(y)))
        y = self.tcn(y)
        y = self.relu(self.bn(y))
        if self.residual and self.downsample is None:
            y = y + x
        elif self.downsample is not None:
            y = y + self.downsample(x)
        return y


class Stream(nn.Module):
    def __init__(self, cin, adjacency, channels=(64, 64, 128)):
        super().__init__()
        blocks = []
        prev = cin
        for cout in channels:
            blocks.append(STGCNBlock(prev, cout, adjacency=adjacency))
            prev = cout
        self.blocks = nn.ModuleList(blocks)
        self.out_channels = prev

    def forward(self, x):
        for block in self.blocks:
            x = block(x)
        return x


class DualStreamSTGCN(nn.Module):
    """Joint stream + motion stream, fused by concatenation before pooling."""

    def __init__(self, joint_in=3, motion_in=4, hidden=(64, 64, 128), num_classes=1,
                 dropout=0.3):
        super().__init__()
        adjacency = build_adjacency()
        self.joint_stream = Stream(joint_in, adjacency, hidden)
        self.motion_stream = Stream(motion_in, adjacency, hidden)
        fused = self.joint_stream.out_channels + self.motion_stream.out_channels
        self.head = nn.Sequential(
            nn.Conv2d(fused, 128, kernel_size=1),
            nn.BatchNorm2d(128),
            nn.ReLU(inplace=True),
            nn.AdaptiveAvgPool2d(1),
            nn.Flatten(),
            nn.Linear(128, 32),
            nn.ReLU(inplace=True),
            nn.Dropout(dropout),
            nn.Linear(32, num_classes),
        )

    def forward(self, joint, motion):           # (N,3,T,V), (N,4,T,V)
        x = torch.cat([self.joint_stream(joint), self.motion_stream(motion)], dim=1)
        return self.head(x).squeeze(1)

    def parameter_count(self):
        return sum(p.numel() for p in self.parameters())
