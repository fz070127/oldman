# A5 边缘端跌倒 Agent

默认读取本地 MP4，在 CPU 上运行 YOLOv8n-pose，把至多两人的姿态逐帧送入 A3，按设备发布 MQTT 事件。启动路径、确认窗口、静止模拟和六段实测见下文。

## 本地运行

在仓库根目录创建 Python 3.10+ 虚拟环境并激活。若已有 A2 的虚拟环境，Windows PowerShell 可直接执行以下命令。

```powershell
.\algo\.venv\Scripts\Activate.ps1
python -m pip install -r edge/requirements.txt
cd edge
python agent.py --config config.yaml
```

默认配置需要 `algo/data/processed/weights/yolov8n-pose.pt` 和 `algo/data/processed/clips/fall-01.mp4`。两者为本地数据产物。已有普通 MP4 时，在 YAML 中填写其路径即可。已有 UR Fall 原始帧时，可在根目录执行以下命令生成默认片段。首次从零准备模型见下方 Linux 安装示例，也可使用 A2 提取脚本下载校验后的同一权重。

```sh
python -m pip install imageio-ffmpeg
python algo/scripts/preview.py --seq fall-01
```

启动本机 broker，在第二个终端订阅后再运行 Agent。安装 Mosquitto 的环境可用以下命令。在 Linux 上，如果已有 mosquitto 服务监听 1883，直接启动订阅即可。

```sh
# 终端 1
mosquitto -p 1883 -v
# 终端 2
mosquitto_sub -h localhost -q 1 -t 'edge/+/event' -t 'edge/+/heartbeat' -v
```

所有配置文件内的文件路径均相对该 YAML。选择 `video_file`、`rtsp_url`、`camera_index` 之一。USB 示例为 `camera_index: 0`。采集设备上报的 fps 无效时使用 `fps_fallback`，应填写相机的实际输出帧率。RTSP 使用 OpenCV FFmpeg 后端，打开、读取超时各 5 秒。实时源断开后每 2 秒重开，重新建轨。实时源只保留最新采样帧，繁忙时会跳帧，A3 根据源帧间隔处理轨迹失联及覆盖率。文件源按视频时钟回放，推理跟不上时逐帧处理，延迟会累积。

`roi` 复用 A3 的家具区域规则。例如 `[{rect: [0.1, 0.3, 0.5, 0.7], action: p1}]`，以人体框底边中点判断，坐标归一化，动作可用 `p1` 或 `suppress`。

## 检测、窗口与时间戳

`detector_wrapper.py` 沿用 A3 的导入方式，将仓库内 `algo/` 加入 `sys.path`，直接导入 `src.fall_detector.FallDetector`。A3 输出增加轨迹 ID 和证据帧，原有阈值和算法配置仍可用于复跑 A4。A5 在实例化时覆盖画面尺寸和静止窗口。同一轨迹、同一证据帧在一次 feed 中同时给出 P1/P0 时，上报最高级一次。P0 的静止判断完全在边缘端完成。P1 的 `stillDurationSec=0` 表示未确认静止，P0 为取证至确认的观察时长。缺失的躯干角保留 JSON null。`occurredAt` 为证据画面的时间，回放使用本次启动时间加媒体偏移，实时源使用采集时间。

**抽帧必须同时改变检测帧率和帧号。** `--downsample 2` 选原始 1、3、5… 帧，分别传入 A3 的 1、2、3…；实时读帧遗漏时保留相应的帧号间隙。30 fps 源默认 1 秒下降窗口、2 秒静止窗口为 30/60 帧，二倍抽帧后为 15/30 帧。A3 的速度、跟踪间隙、静止覆盖率均沿用这个有效 fps。本机推荐先按默认全帧复现，15 fps 的漏检变化见实测。

```sh
python agent.py --config config.yaml --downsample 2
```

本地文件自然结束时调用 A3 的 `finish()`，对剩余疑似事件最多补出 P1，日志标记 `reason=file_eof`。例如默认 160 帧的 fall-01 在 EOF 报 P1。连续源断流、手动退出均不执行 EOF 补报。下方时延取 `reason=stream` 的在线发报。

## MQTT、断网演示与恢复

事件发往 `edge/{deviceNo}/event`。创建事件时只生成一次 UUID，先提交完整 JSON 至 SQLite，再打印“本地已报警”并输出终端 BEL。单个发送线程按 `created_at, rowid` 取最旧未发事件，QoS 1 收到 PUBACK 后才置 `sent=1`。网络线程自动重连，本地数据库在进程重启后继续使用。broker 已收到、进程尚未落下 ACK 就重启时，可能收到相同 ID 的重复投递，后端以 `eventId` 幂等。PUBACK 表示 broker 已确认；业务落库需由后端订阅端验证。[Paho 文档](https://github.com/eclipse-paho/paho.mqtt.python)

每个设备独占 client ID 和数据库。库内保留最近 1000 条事件，含已发记录；超过上限时删除最旧记录，并记录其 ID 及 sent。断网期间心跳跳过，事件仍落库和本地报警。默认每 30 秒发送 `edge/{deviceNo}/heartbeat`，fps 为本周期实际推理帧数除以墙钟秒数，cpu/mem 为主机使用百分比。短片测试可把 `heartbeat_sec` 设为 1。

1. 订阅事件并启动 Agent。播放到跌倒前停止本机测试 broker，继续播放。
2. 在 `edge/` 中执行下列查询。日志应有本地报警，数据库有 `sent=0`。有限 MP4 结束后进程会继续等候补传。
3. 恢复同地址、端口的 broker，查看 PUBACK 日志及数据库。原 UUID 对应记录变为 1；等待补传的 MP4 进程随后退出。演示时若订阅端先于恢复投递离线，普通非持久订阅可能错过消息，可同时核对 broker 日志。

```sh
python -c "import sqlite3; print(sqlite3.connect('.cache/EDGE-0001.sqlite3').execute('SELECT id,sent,created_at FROM events ORDER BY created_at,rowid').fetchall())"
```

## 多设备模拟

在 `edge/` 中运行。每个设备有自己的 MQTT 连接和 SQLite，模拟编号 EDGE-0001 至 EDGE-0005 对应 E001 至 E005。使用单机默认 EDGE-0001 的 Agent 与模拟器需错开运行，或为 Agent 设置另一设备号和库路径。

```sh
python tools/simulator.py --devices 5 --interval 300 --mqtt-host localhost
python tools/simulator.py --devices 5 --mock --interval 5 --mqtt-host localhost
```

视频模式从 A1 清单随机抽取 fall 或 adl 的 RGB 帧，运行姿态推理和 A3；抽到无事件序列继续抽取，有判定时上报一条。每台设备按 interval 发起一轮，推理耗时超过间隔时顺延。五设备共享模型并串行调用推理，以限制资源开销。mock 模式无需视频、权重和关键点缓存，每个间隔每台设备发布一条随机事件。Ctrl+C 停止。

## RK3588 安装和 systemd

以下以 64 位 Debian/Ubuntu、Python 3.10+ 为例，假设仓库位于 `/opt/fall-agent` 且服务用户 `edge` 可读源码、可写 `edge/.cache`，USB 输入还需有相机设备权限。当前 Agent 使用 CPU PyTorch 姿态推理。板上需安装与系统 Python/架构匹配的 torch、torchvision wheel。

```sh
cd /opt/fall-agent
sudo apt-get install python3-venv libgl1 libglib2.0-0 ffmpeg mosquitto-clients curl
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r edge/requirements.txt
mkdir -p algo/data/processed/weights
curl -fL https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n-pose.pt -o algo/data/processed/weights/yolov8n-pose.pt
echo 'c6fa93dd1ee4a2c18c900a45c1d864a1c6f7aba75d84f91648a30b7fb641d212  algo/data/processed/weights/yolov8n-pose.pt' | sha256sum -c -
python edge/agent.py --config edge/config.yaml
```

将 YAML 设为实际 RTSP/USB 源和 broker 地址。服务示例保存为 `/etc/systemd/system/fall-edge.service`。

```ini
[Unit]
Description=Fall detection edge agent
After=network.target

[Service]
Type=simple
User=edge
SupplementaryGroups=video
WorkingDirectory=/opt/fall-agent/edge
ExecStart=/opt/fall-agent/.venv/bin/python agent.py --config config.yaml
Environment=PYTHONUNBUFFERED=1
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
```

```sh
sudo systemctl daemon-reload
sudo systemctl enable --now fall-edge
journalctl -fu fall-edge
```

**ONNX → RKNN**。在支持 RKNN-Toolkit2 的 Linux 转换主机上，以下命令使用 Rockchip 提供的 YOLOv8n-pose ONNX 和对应转换脚本。得到的 RKNN 供后续 NPU 接入；当前 Agent 的 `detector.weights` 使用 PT。板端运行时和后处理仍需上板验证。[Rockchip 姿态模型转换说明](https://github.com/airockchip/rknn_model_zoo/blob/main/examples/yolov8_pose/README.md)

```sh
python -m pip install rknn-toolkit2
git clone https://github.com/airockchip/rknn_model_zoo.git
cd rknn_model_zoo/examples/yolov8_pose/model
bash download_model.sh
cd ../python
python convert.py ../model/yolov8n-pose.onnx rk3588 fp
```

## 复现实测

在 `edge/` 下运行。splits 需要 A2 的 70 段关键点 NPZ（从仓库根目录执行 `python algo/scripts/extract_keypoints.py --resume` 可生成）。video 需要原始 RGB 帧、权重、本机 broker 和 ffmpeg 或 imageio-ffmpeg，不读取 NPZ。video 会创建隔离库，记录每段 MP4 和 Agent 日志到 `.cache/bench/`，输出每段 JSON。在同一 broker 上串行运行两档以避免测试 client ID 冲突。

```sh
python tools/benchmark.py splits --hold-sec 0
python tools/benchmark.py splits --hold-sec 4
python tools/benchmark.py video --mqtt-host localhost
python tools/benchmark.py video --mqtt-host localhost --downsample 2
```

## 2026-11-19 验收结果

**选 C，A5 的 2 秒窗口作为演示和评测配置。实测不支持对外承诺 3 秒。** A4 的主路径证据帧时延中位数为 19 帧，验证集两个有 onset 的检出样本均值为 27 帧。A5 分开记录首次证据、A3 真正 emit、MQTT publish 及独立订阅端到达时刻。原始逐段数据、完整 payload 及两种窗口的重测结果保存在 [a5.json](reports/a5.json)。

### 连续流时延

将每段完整原始 RGB 序列编码为 30 fps MP4，尾端保持最后一幅图像 4 秒，逐帧重新推理。延长部分是静止模拟。测量起点是首帧播放时钟加 `(onset-1)/30`，终点分别为已获 PUBACK 的 Paho publish 调用和独立订阅进程收到消息。两者使用同机单调时钟。计时含解码、积压、姿态推理、判定、SQLite 和发布，排除模型启动。对每段、每档各取一次有效运行；不同负载下会波动。

| 段号 | onset | 全帧证据→emit 帧号 | onset→证据 / 视频秒 | 全帧级别 | onset→发布 / 墙钟秒 | onset→订阅 / 墙钟秒 | 二倍抽帧 onset→发布 / 墙钟秒 |
|---|---:|---:|---:|---|---:|---:|---:|
| fall-01 | 90 | 111→175 | 0.700 | P1 | 5.603 | 5.604 | 2.935 |
| fall-05 | 86 | 105→165 | 0.633 | P0 | 8.205 | 8.206 | 2.686 |
| fall-09 | 127 | 143→203 | 0.533 | P1 | 9.524 | 9.525 | 2.575 |
| fall-06 | 25 | 41→101 | 0.533 | P0 | 6.499 | 6.500 | 2.590 |
| fall-10 | 41 | 69→129 | 0.933 | P0 | 7.394 | 7.395 | 漏检 |
| fall-02 | 40 | 65→125 | 0.833 | P0 | 7.263 | 7.265 | 2.879 |

全帧 6/6 发报，发布中位数 7.329 秒。二倍抽帧 5/6 发报，检出的五段中位数 2.686 秒。所有已发事件均在连续 feed 产生。fall-01 在轨迹失联后发 P1，两秒配置下仍在源帧 175 发出。fall-05 第 105 帧出现证据，第 165 帧在模拟连续流中确认 P0，订阅端收到 `stillDurationSec=2.0`。原片只到 151 帧，后续观测不能用于证明真实老人持续静止。六段为指定时延样本；全量 val/test 召回另列。

### 误报与降采样

每个划分含 6 段 fall 和 8 段 ADL。下表为有任意告警的序列计数；原片 EOF 与尾帧保持 4 秒两种实验在这些列相同。

| 检测帧率 | 静止窗口 | val 检出 | val 误报 | test 检出 | test 误报 |
|---|---:|---:|---:|---:|---:|
| 30 fps | 3 秒或 2 秒 | 6/6 | 2/8 | 2/6 | 2/8 |
| 15 fps | 3 秒或 2 秒 | 4/6 | 2/8 | 2/6 | 2/8 |

15 fps 在验证集新增漏检 fall-19、fall-25。val 的误报为 adl-36、adl-37，test 为 adl-10、adl-11。**原片 EOF 口径下，缩窗使 test 的 P0 误报从 0/8 升至 2/8**，两档 fps 均如此；这两段原先已经报 P1。原片 val 两种窗口均无 P0。保持尾帧时，两种窗口、两档 fps 均能在 fall-29、fall-05 产出 P0，也都把 adl-10、adl-11 报成 P0。现场启用较短确认窗口前，需要有完整跌倒后观察期的正负样本来评估 P0 代价；YAML 设为 3.0 可复现 A3 窗口。

### 资源与网络

测试机为 Windows 11 build 26200，i7-14650HX，16 核 24 线程，系统可见内存 15.71 GiB，Python 3.12.5、CPU PyTorch 2.15.0、Ultralytics 8.4.215、4 推理线程，640×480 输入、imgsz 640。独立 aMQTT 0.11.3 broker 和 Paho 2.1.0 订阅端均在本机。以下为六段的每段均值范围，RSS 和主机 CPU 峰值为采样最大值。CPU 每 0.5 秒采样，Agent CPU 按全部逻辑核归一化并包含 Windows venv 启动子进程。

| 模式 | 实际推理 fps | Agent CPU | 整机 CPU 均值 | 整机瞬时峰值 | Agent RSS 峰值 |
|---|---:|---:|---:|---:|---:|
| 全帧 | 13.90–18.11 | 15.85–16.81% | 26.13–37.66% | 86.3% | 437.93 MiB |
| 二倍抽帧 | 15.02–15.08 | 14.90–15.19% | 22.93–30.88% | 84.8% | 439.57 MiB |

Agent 的平均 CPU 低于 80%；整机瞬时负载曾超出 80%。全帧运行速度低于源帧率，文件播放积压计入上述墙钟时延。实物 RTSP、USB 和 RK3588 的吞吐、端到端时延仍待现场采集。

## ST-GCN 验证与模型监控

`config.yaml` 中的 `detector.stgcn.enabled` 默认关闭。准备训练权重、校准阈值并完成验证后可手动开启。模型使用连续 30 帧，启用时将 `downsample` 设为 1。姿态推理设备可通过 `detector.device` 选择。

`detector.consensus` 对模型主动触发路径使用连续多窗均分，规则事件的模型确认采用单窗重评分。桌面版 C2 参数降低误报时也降低了检出，启用前用当前权重和数据重新标定。可运行 `python tools/verify_c2.py` 检查配置和触发逻辑。

配置 `monitor.url` 和有 `model-monitor:record` 权限的令牌后，边缘端会异步上报模型分数及从证据画面到发报的耗时。拥有 `dashboard:read` 的账号可查询快照，配置基线与清空记录需要 `model-monitor:write` 权限。监控数据保留在服务内存中。

断开真实 broker 后，五台 mock 设备各积压 4 条、共 20 条。重启 broker，20 条均按各设备的入库顺序送达，逐条比对 ID 和完整 JSON 一致，SQLite 均由 0 变 1。另在默认 fall-01 MP4 播放中停 broker，终端记录“本地已报警”，ID `73e4bf62-87ae-48d6-b659-1def421e212c` 先以 0 入库；恢复后订阅端收到原 payload，PUBACK 后置 1。该 payload 已通过 M5 的 `IngestPayload.model_validate_json`。独立冷启动试验中，新 Publisher 打开原数据库也送达了原 ID。连续插入 1001 条时淘汰最旧一条、保留 1000 条。五设备 mock 和单设备真实 UR Fall RGB 模式均已由订阅端验收。
