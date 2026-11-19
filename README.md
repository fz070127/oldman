# 银铃守护 —— 独居老人跌倒行为智能检测预警系统

> 面向独居/空巢老人的非接触式跌倒检测与多级预警平台。
> 边缘端实时识别跌倒 → 云端分级告警 → 家属 / 网格员 / 社区大屏三级响应闭环。

用**一个摄像头 + 一台边缘盒子**，在**不上传原始视频**的前提下，
把"老人摔倒后无人知晓"的平均发现时间从**数小时**压缩到**10 秒内**。

## 目录

| 路径 | 内容 |
|---|---|
| [backend/](backend/) | FastAPI 服务：接口、数据库、告警流转 |
| [frontend/](frontend/) | Vue 3 Web 管理端 + 社区大屏 |
| [algo/](algo/) | 跌倒检测算法：数据管线、姿态提取、判定引擎 |
| [tools/](tools/) | 数据获取工具 |

`edge/`（边缘推理 Agent）、`frontend-h5/`（uni-app 家属端）、`deploy/`（容器编排）
尚未开工。

## 快速开始

### 后端

需要 PostgreSQL 16 与 Redis 7，Python 3.11–3.12。

```bash
cd backend
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e .
cp .env.example .env
# 编辑 .env，至少填写 JWT_SECRET 和 DEMO_SEED_PASSWORD
.venv/Scripts/python.exe -m alembic upgrade head
.venv/Scripts/python.exe -m app.db.seed
.venv/Scripts/python.exe -m uvicorn app.main:app --reload --loop asyncio:SelectorEventLoop
```

`.env` 的完整变量表见 [backend/README.md](backend/README.md)。

服务默认监听 8000，`/health` 返回存活状态，`/docs` 是 Swagger UI。

演示账号 `admin`、`guardian01`–`guardian20`、`community01`–`community05`、
`family01`–`family20`，密码取首次填充数据时的 `DEMO_SEED_PASSWORD`。

演示前先刷新一次演示数据（恢复设备心跳、重置待确认告警时间）：

```bash
.venv/Scripts/python.exe -m app.db.seed --refresh-demo
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

开发环境默认启用 mock（`VITE_USE_MOCK=true`），不需要后端即可跑通全部页面。

### 算法

数据管线读取 UR Fall 数据集，按 [algo/README.md](algo/README.md) 放置后执行：

```bash
cd algo
python -m pip install -r requirements.txt
python scripts/prepare_ur_fall.py
python scripts/extract_keypoints.py --workers 2
python scripts/analyze_keypoints.py
```

## 技术栈

| 层 | 选型 |
|---|---|
| 后端 | Python 3.11+、FastAPI、SQLAlchemy 2.0 async、Alembic、asyncpg、Pydantic v2 |
| 数据 | PostgreSQL 16、Redis 7、MinIO、EMQX (MQTT) |
| 前端 | Vue 3.4 + TypeScript、Vite 5、Element Plus、Pinia、ECharts 5 |
| 算法 | YOLOv8n-pose、ByteTrack、规则状态机（可选 ST-GCN） |

## 接口约定

- 统一响应体 `{code, message, data, traceId}`，业务错误返回 HTTP 200 加业务码
- JSON 字段一律 camelCase
- 时间戳为带时区的 ISO 8601（`+08:00`）

## 数据集与许可

算法部分使用 **UR Fall Detection Dataset**（University of Rzeszów），
许可为 **CC BY-NC-SA 4.0**，仅限非商业学术研究。数据集不随仓库分发，
需自行获取。

## 目录结构

```
.
├── backend/          # FastAPI 服务
├── frontend/         # Vue3 Web 管理端 + 大屏
├── algo/             # 数据管线、姿态提取、判定引擎
├── tools/            # 数据获取工具
├── edge/             # 边缘推理 Agent（未开工）
├── frontend-h5/      # uni-app 家属端（未开工）
└── deploy/           # Docker Compose、Nginx（未开工）
```
