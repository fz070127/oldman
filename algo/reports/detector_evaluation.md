# A3 完成

`feat/algo-a3` 从 `dev` 创建。冻结验证集检出 6/6 段跌倒，ADL 误报 2/8 段，P0 为 0。冻结测试集检出 2/6 段跌倒。

### 文件清单

| 文件 | 用途 |
|---|---|
| [`src/features.py`](../src/features.py) | 七项特征、人体框几何、缺失值处理 |
| [`src/fall_detector.py`](../src/fall_detector.py) | 多人关联、状态机、两条规则、恢复站立与家具 ROI 抑制 |
| [`configs/detector.yaml`](../configs/detector.yaml) | 两条路径、静止覆盖、跟踪、恢复和家具 ROI 参数 |
| [`scripts/run_detector.py`](../scripts/run_detector.py) | 单段缓存推理和五字段 `signals` JSON |
| [`scripts/evaluate_detector.py`](../scripts/evaluate_detector.py) | 冻结划分评估、逐段输出、时延与耗时 |

在 `algo/` 下运行，Windows 本次环境使用 `.venv\Scripts\python.exe`。

```powershell
python scripts/run_detector.py --seq fall-01
python scripts/evaluate_detector.py --output data/processed/a3-validation.json
```

### 关键代码

四个肩髋点达到置信度阈值时，以肩中点和髋中点的连线求水平夹角。点缺失时返回 `None`，JSON 序列化为 `null`。框内没有 `hip_y`，因此 `body_height` 采用 `bbox_h / frame_height`。T1/B1 的 `height_drop` 是同一轨迹在近 1 秒相对峰值框高的下降比例，`v_drop` 取该峰值之后下降速率的最大值。主路径和框兜底共用这套框特征。

```python
height = box.height / frame_height if box else None
v_drop = None
if box and previous_box and elapsed_sec and elapsed_sec > 0:
    v_drop = (previous_box.height - box.height) / frame_height / elapsed_sec
```

主路径要求降幅 `>0.45`、速率过线、躯干角 `<40°`、宽高比 `>1.2`、17 点平均置信度 `≥0.30`。姿态证据不足时，框兜底要求降幅 `>0.50`、速率阈值乘 `1.20`、宽高比 `>1.40` 且框底进入画面底部 15%。

```python
if fall.signal == "keypoints" and fall.roi_action is None and still_lying:
    boxes = [s.box for s in track.samples if s.frame >= fall.sample.frame] + [sample.box]
    coverage = len(boxes) / (elapsed_frames + 1)
    motion = features.motion if elapsed_frames == self.motion_frames else center_motion(boxes)
    if coverage >= cfg.motion_coverage_min and motion is not None and motion < cfg.motion_max:
        track.state = State.CONFIRMED
        self._emit(fall, sample, "P0")
```

**B 路径不产 P0。** 只有以可靠躯干角进入倒地状态的事件可以升级。P0 还需观察满 3 秒、框覆盖 `≥80%`、中心最大位移低于起始框对角线的 0.30 倍，且终点仍有倒地形态。可靠终点躯干角在 `40°` 或以上时保留 P1。恢复站立时撤销 3 秒内的候选。家具 ROI 根据倒地框底边中点匹配，可抑制事件或限制为 P1。UR Fall 基准的 ROI 列表为空。

离线结果中的 P1 帧是首次满足倒地条件的证据帧。状态机会等待恢复观察结束、轨迹超时或片段结束再保留该事件，因此评估里的帧差衡量证据出现时延。实时发报会另受观察窗口影响。`confidence` 是检测置信度摘要，主路径取人体框和关键点均值的平均，框兜底取人体框置信度。

### 关键点重建后的核对

- 五段试提取共 732 帧。双进程全量用时 533.25 秒，`--verify` 输出 `verified 70 sequences, 11936 frames`。
- 每份 NPZ 含 7 个键。A2 校验通过，非有限值和 `-1` 填充值均为零。全量检出 10,450 帧（87.55%），低置信帧 1,644，多人帧 153。与 A2 的 70 行逐段质量表和 30 行 IMU 窗口统计逐行吻合。
- 254 个明确卧地帧中，有框 218，17 点平均置信度 `≥0.30` 有 178，肩髋四点均 `≥0.30` 有 150。13 个完整 IMU 窗口按原始值复算为 `0.808508 → 0.575647`。先把逐段结果保留三位小数再求均值，会得到派单中的 `0.808 → 0.576`。
- `fall-13` 有 45/85 帧原始检出人数至少为 2。左侧旁观者在 43 个能定位到其人体框的多人帧中保持同一 ID，包含三次位于第一槽的情况。跌倒者的主体框保持另一 ID，个别低置信局部框形成临时轨迹。

### val 上的实际结果表

冻结 CSV 的实际分组为 train 42、val 14、test 14。val 含 6 段跌倒、8 段 ADL。表中 `—` 表示无检测或无已批准起始帧。

| 段号 | 等级 / 路径 | 首报帧 | 批准起始帧 | 时延（帧） |
|---|---|---:|---:|---:|
| fall-19 | P1 / 框兜底 | 59 | — | — |
| fall-03 | P1 / 框兜底 | 187 | 152 ±8 | 35 ±8 |
| fall-18 | P1 / 主路径 | 42 | — | — |
| fall-29 | P1 / 主路径 | 75 | — | — |
| fall-05 | P1 / 主路径 | 105 | 86 | 19 |
| fall-25 | P1 / 框兜底 | 70 | — | — |
| adl-36 | P1 / 主路径 | 248 | — | — |
| adl-13 | — | — | — | — |
| adl-03 | — | — | — | — |
| adl-04 | — | — | — | — |
| adl-37 | P1 / 主路径 | 267 | — | — |
| adl-25 | — | — | — | — |
| adl-31 | — | — | — | — |
| adl-14 | — | — | — | — |

时延只统计已批准且成功检出的段，分布为 19 和 35 帧，均值与中位数均为 27 帧（0.90 秒）。`fall-03` 的起始帧有 ±8 帧不确定度，对应时延 27–43 帧（0.90–1.43 秒）。

### 主路径与兜底路径的命中分布

| 数据集 | 类别 | 主路径命中段数 | 框兜底命中段数 | 任意路径检出段数 |
|---|---|---:|---:|---:|
| val | fall | 3 | 3 | 6/6 |
| val | ADL | 2 | 0 | 2/8 |
| test | fall | 2 | 0 | 2/6 |
| test | ADL | 2 | 0 | 2/8 |

test 只跑了一次。开发使用 train/val，冻结测试由最终配置统一运行。命中的两段为 `fall-09`（16 帧）和 `fall-01`（21 帧），时延均值 18.5 帧（0.617 秒），ADL 的 P0 为 0。`fall-01` 在第 111 帧输出 P1，五字段齐全，`adl-01` 结果为空。该次测试保存到 `data/processed/a3-test-final.json`。

### 与预期的偏差

- 验证集达到 `≥4/6` 跌倒检出和 ADL `P0 ≤1` 的门槛。两段 ADL P1 分别为 `adl-36` 和 `adl-37`。测试集有四段跌倒漏报，且框兜底命中为 0。
- val 检出的跌倒在 P1 后仅剩 15–46 帧，少于确认所需的 90 帧。P0 升级、移动拦截、半躺终点、缺帧、恢复、限级和抑制均通过合成轨迹检查。真实 val 和 test 的输出均为 P1。
- 抽检 `fall-03` 第 187 帧（框比 2.02、均置信度 0.350，肩髋角缺失）、`fall-05` 第 105 帧（角 2.81°、框比 1.29）和 `fall-25` 第 70 帧（框比 1.75、均置信度 0.262），触发帧与框和骨架叠加一致。骨架视频在 `data/processed/overlays/`。
- 将 `bbox_floor_margin` 从 0.15 改为 0.00 的单独配置，使 `fall-03` 从第 187 帧框兜底改为第 190 帧主路径。报告结果对应默认 YAML。
- 验证集单段读取 NPZ 加推理最慢 13.031 毫秒，测试集最慢 25.571 毫秒。`fall-03` 单段 CLI 含 Python 启动耗时 261.1 毫秒。

### 待确认问题

- A4 的验收文档可否按冻结 CSV 登记为 train 42、val 14、test 14，并把 val ADL 分母写为 8？
- A4 是否沿用框高代理和离线 P1 证据帧时延，并另列实时发报时延？
