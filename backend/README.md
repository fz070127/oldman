# 银铃守护 API

运行环境为 Python 3.11。健康检查使用 PostgreSQL 16 和 Redis 7，分别执行 `SELECT 1` 和 `PING`。两项检查并行执行，各自的等待上限为 2 秒。服务启动时只创建连接池和客户端，因此也可以在依赖离线时启动。

## 本地运行

在 PowerShell 进入后端目录并创建虚拟环境。若 Python 3.11 未注册到 Windows 启动器，第一条 Python 命令可换成该解释器的完整路径。

```powershell
Set-Location 'F:\独居老人\backend'
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

首次运行时复制示例配置。按本地服务修改 `.env` 中的 `DATABASE_URL` 和 `REDIS_URL`。系统环境变量优先于文件。`CORS_ORIGINS` 使用 JSON 字符串数组，`NOTIFY_PROVIDER` 可取 `mock` 或 `aliyun`。Uvicorn 命令行默认监听 8000，需要指定端口时使用 `--port`。也可运行 `.\.venv\Scripts\python.exe -m app.main` 读取 `APP_PORT`。

## 验收

另开 PowerShell，在同一目录运行：

```powershell
curl.exe -i http://localhost:8000/health
curl.exe -i http://localhost:8000/api/v1/missing
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\ruff.exe check .
```

- 健康检查返回 HTTP 200 和 `code=0`。两个依赖均连通时，`data` 为 `{"status":"up","db":"up","redis":"up"}`。离线的依赖显示 `down`，整体 `status` 仍为 `up`。
- 未知路径返回 HTTP 200、`code=1004`、`data=null`。两个请求的响应体都含有与本次响应头 `X-Trace-Id` 相同的 12 位十六进制标识。
- 在浏览器访问 [Swagger UI](http://localhost:8000/docs) 可查看根路径健康接口；后续业务模块统一挂到 `/api/v1`。自动化测试使用替身覆盖数据库和 Redis 各自在线、离线的组合。

## PostgreSQL 数据层（M2）

在后端目录激活 Python 3.11 虚拟环境，确保 `DATABASE_URL` 指向已创建的开发库（连接串使用 `postgresql+asyncpg://`），然后执行：

```powershell
python -m alembic upgrade head
python -m alembic current
python -m app.db.seed
python -m app.db.seed
```

初始迁移为 `0001`，包含 12 张业务表。空库的两次 seed 分别输出新增 500、0 条告警。46 个联调账号的密码均为 `123456`，使用 bcrypt 独立加盐；另外一条禁用的 `SYSTEM` 记录用于系统处置流水的外键。事件时间、设备心跳和 PENDING 倒计时均以首次填充时刻为基准，重跑保留已有处置记录。100 位老人中，5 位在册和 5 位暂停老人没有设备，另有 5 位绑定离线设备。

设置 `TEST_DATABASE_URL` 后运行 `python -m pytest -q` 可执行数据库集成测试。测试账号需要在测试库创建 schema 的权限，每个测试在独立 schema 内执行，结束时回滚。未配置该变量时 pytest 会跳过数据库集成测试。若需手工演练回滚，先将 `DATABASE_URL` 指向一次性验收库，再运行 `python -m alembic downgrade base`，该命令会删除 12 张业务表及其数据。

## 容器运行

```powershell
docker build -t silver-bell-backend:m1 .
docker run --rm --env-file .env -p 8000:8000 silver-bell-backend:m1
```

镜像以非 root 用户启动。容器中的连接地址应使用依赖服务的网络名称，连接 Windows 宿主机可使用 `host.docker.internal`。如果修改 `APP_PORT`，端口映射右侧也要改为相同值。
