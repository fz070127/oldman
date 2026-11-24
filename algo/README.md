# A1 · UR Fall 数据管线

每行索引代表一段完整的 cam0 RGB 序列。PNG 保留在原始位置。以假定的 30 fps 计算时长，本批数据共 70 段、11,936 帧。

## 数据位置和运行方式

默认读取项目根目录下的 `sumanpunshi/ur-fall-detection-dataset/versions/1/UR_data/`。保留下列层次即可，脚本会找到含 PNG 的内层目录。

```text
UR_data/
  Fall/fall-01-cam0-rgb/fall-01-cam0-rgb/fall-01-cam0-rgb-001.png
  ADL/adl-01-cam0-rgb/adl-01-cam0-rgb/adl-01-cam0-rgb-001.png
```

在项目根目录打开终端，使用 Python 3.9 或更高版本执行以下命令。Windows 安装了 Python Launcher 时也可以用 `py -3.12` 代替 `python`。

```sh
cd algo
python -m pip install -r requirements.txt
python scripts/prepare_ur_fall.py
python scripts/preview.py --seq fall-01
python scripts/make_hard_negatives.py
python scripts/split_dataset.py
```

原始数据放在其他位置时，使用 `python scripts/prepare_ur_fall.py --raw-root "D:/datasets/UR_data"`。准备脚本检查 PNG 文件名和帧号，遇到空序列、重号或断号会报错。它在扫描时仅读取目录，图像解码发生在预览阶段。

## 总清单

`data/labels/ur_fall.csv` 使用 UTF-8 编码，每段一行。

| 字段 | 含义 |
|---|---|
| `seq_id` | 唯一序列编号，如 `fall-01`、`adl-30` |
| `label` | 原始文件夹给出的整段类别，取值为 `fall` 或 `adl` |
| `frame_dir` | 含 PNG 的目录。相对路径以 `algo/` 为基准，Windows 跨盘时使用绝对路径 |
| `frame_count` | 实际 PNG 帧数 |
| `fps` | 假定帧率 30，序列时长（秒）为 `frame_count / fps` |
| `fall_onset` | 人工确认的跌倒起始帧，使用文件名末尾的帧号，从 1 开始；初始为空 |
| `confusable_type` | 人工确认的易混淆动作类型，初始为空 |
| `note` | 人工备注，初始为空 |

再次扫描时，同一 `seq_id` 的三个标注字段会保留。准备脚本按类别打印序列数、帧数以及逐段时长的最短值、中位数和最长值。

## 预览和难例

`preview.py --seq fall-01` 按数字帧号顺序编码，默认输出 `data/processed/clips/fall-01.mp4`（H.264，640×480，30 fps）。可用 `--output demo.mp4` 指定目标文件。脚本优先使用 PATH 中的 FFmpeg，也支持 `imageio[ffmpeg]` 附带的编码器。

复核 ADL 时，把 `--seq` 改为相应编号。确认动作后，在 `configs/confusable.yaml` 中按 `adl-xx: sit` 的格式填一行，用实际编号替换 `xx`。支持 `sit`（坐下）、`lie`（躺下）、`bend`（弯腰）和 `squat`（蹲下）。再次运行 `make_hard_negatives.py`，会从总清单取出选定行，并将配置的动作写入 `data/labels/hard_negative.csv` 的 `confusable_type` 列。配置初始为空，因此首次输出只有表头。

## 训练、验证与冻结测试集

| 成员清单 | fall | adl | 总序列数 |
|---|---:|---:|---:|
| `data/splits/train.csv` | 18 | 24 | 42 |
| `data/splits/val.csv` | 6 | 8 | 14 |
| `data/splits/test.csv` | 6 | 8 | 14 |

脚本按类别排序序列编号，再用固定随机种子 42 洗牌。每段完整归属一个集合。三个清单记录 `seq_id,label`，按 `seq_id` 关联总清单即可取得原始帧路径和最新标注。训练时先选定集合，再在该集合内从各段取帧或切窗口。评估测试集难例时，取难例编号与测试集编号的交集。

三个清单一次生成。当前数据已附带冻结划分，再运行默认命令将以非零退出码拒绝覆盖。需要复验首次生成过程时，指定一个尚不存在的目录，例如 `python scripts/split_dataset.py --output-dir data/splits-check`；在同一路径第二次执行即可验证冻结保护。

## A2 · 提取、质量分析和起始帧复核

在 `algo/` 下使用 Python 3.12（本次实测），原始 PNG 和加速度 CSV 共用项目根目录下的 `sumanpunshi/`。独立 Git 工作树可将其链接到已有数据目录。首次提取自动下载官方 YOLOv8n-pose 权重，校验 SHA-256 后缓存于 `data/processed/weights/`。

本次全量运行使用 Ultralytics 8.4.215、PyTorch 2.15.0+cpu、OpenCV 5.1.0，按序列使用两个 CPU 进程，每次向模型传入连续 8 帧。报告中的毫秒/帧是离线全量吞吐指标。

```powershell
python -m pip install -r requirements.txt
python scripts/extract_keypoints.py --limit 5
python scripts/extract_keypoints.py --workers 2
python scripts/extract_keypoints.py --verify
python scripts/visualize_keypoints.py --seq fall-01
python scripts/annotate_onset.py
python scripts/analyze_keypoints.py
```

全量命令会重新计时并生成 `data/processed/extraction_time.json`。中断后可用 `--resume --workers 2` 重建缺失或残损的段；续跑控制台只汇总该次处理的帧。如需复测完整耗时，运行一次不带 `--resume` 的全量命令。

姿态数组位于 `data/processed/keypoints/`，可用 `np.load(path, allow_pickle=False)` 读取。帧号从 1 起，`n_people` 保存筛选最高两人前的数量。两个槽位按每帧检测分排序，空槽置零；跨帧跟踪时需另外建立身份关联。骨架视频写入 `data/processed/overlays/`。

起始帧复核使用 `python scripts/preview.py --seq fall-01` 生成的原始画面视频。在 `reports/onset_review.csv` 填写 1 起帧号、观察依据和复核来源。`frame` 是开始失衡的第一帧，`lying_from` 是可明确观察到卧地且延续至片尾的抽样起帧。`review` 如实填写「人工逐帧复核」或「未人工逐帧复核」；边界不确定度写入 `uncertainty_frames`。取得人工复核登记许可后标记 `approved=1`，执行 `python scripts/annotate_onset.py --apply` 写回相应 `fall_onset`。冻结划分直接引用序列 ID。

两份报告分别见 [关键点质量](reports/keypoint_quality.md) 和 [起始帧记录](reports/onset_annotation.md)。

## 时序模型训练与导出

以下命令从项目根目录执行。训练前需安装 `algo/requirements.txt` 并按上文准备关键点。

```sh
python algo/scripts/build_windows.py --train-stride 3 --post-margin 15
python algo/scripts/train_stgcn.py --hidden 48 48 96 --lr 2e-4 --weight-decay 5e-4 --dropout 0.5 --pos-weight-cap 3 --epochs 250 --patience 40 --flip-augment
python algo/scripts/train_lstm.py
python algo/scripts/export_onnx.py --model pose
python algo/scripts/export_onnx.py --model stgcn
```

`--scheduler plateau` 可用于两个训练脚本，按验证损失降低学习率。导出的 `yolov8n-pose.onnx` 和 `stgcn_static.onnx` 位于 `algo/data/processed/onnx/`。图片检测使用姿态模型提取关键点，使用 ST-GCN 提供可选的参考分。模型文件可由命令生成，部署读取方式见 [部署说明](../deploy/README.md)。

- `split_dataset_721.py` 将 49/14/7 划分写到 `data/splits-721/`，可用 `build_windows.py --split-dir` 读取并另存窗口。
- `evaluate_fusion.py`、`bench_models.py`、`cross_validate.py` 用于比较规则与模型融合、基准耗时和交叉验证。
- `compare_pose_models.py` 对比姿态模型，候选模型与权重位置见 `configs/pose_compare.yaml`。运行 `extract_keypoints.py --model <权重文件名> --out <目录>` 可把候选模型的关键点输出到独立目录。
- `dump_dense_scores.py` 生成稠密滑窗分数，`tune_consensus.py --config algo/data/processed/c2/consensus.local.json` 在验证集上定阈值，`evaluate_consensus.py --config algo/data/processed/c2/consensus.local.json` 独立复算；`compare_c_stages.py` 用于阶段对比。
