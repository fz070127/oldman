# 银铃守护 API

支持 Python 3.11 和 3.12。健康检查使用 PostgreSQL 16 和 Redis 7，分别执行 `SELECT 1` 和 `PING`。两项检查并行执行，各自的等待上限为 2 秒。服务启动时只创建连接池和客户端，因此也可以在依赖离线时启动。

## 本地运行

在 PowerShell 进入后端目录并创建虚拟环境。若 Python 3.12 未注册到 Windows 启动器，第一条 Python 命令可换成该解释器的完整路径。

```powershell
Set-Location backend
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
Copy-Item .env.example .env
$env:JWT_SECRET = .\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(32))"
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
.\.venv\Scripts\ruff.exe format --check .
```

- 健康检查返回 HTTP 200 和 `code=0`。两个依赖均连通时，`data` 为 `{"status":"up","db":"up","redis":"up"}`。离线的依赖显示 `down`，整体 `status` 仍为 `up`。
- 未知路径返回 HTTP 200、`code=1004`、`data=null`。两个请求的响应体都含有与本次响应头 `X-Trace-Id` 相同的 12 位十六进制标识。
- 在浏览器访问 [Swagger UI](http://localhost:8000/docs) 可查看根路径健康接口；后续业务模块统一挂到 `/api/v1`。自动化测试使用替身覆盖数据库和 Redis 各自在线、离线的组合。

## PostgreSQL 数据层（M2）

在后端目录激活虚拟环境，确保 `DATABASE_URL` 指向已创建的开发库（连接串使用 `postgresql+asyncpg://`），然后执行：

```powershell
python -m alembic upgrade head
python -m alembic current
python -m app.db.seed
python -m app.db.seed
```

初始迁移为 `0001`，包含 12 张业务表。空库的两次 seed 分别输出新增 500、0 条告警。46 个联调账号的密码均为 `123456`，使用 bcrypt 独立加盐；另外一条禁用的 `SYSTEM` 记录用于系统处置流水的外键。事件时间、设备心跳和 PENDING 倒计时均以首次填充时刻为基准，重跑保留已有处置记录。100 位老人中，5 位在册和 5 位暂停老人没有设备，另有 5 位绑定离线设备。

演示前运行 `python -m app.db.seed --refresh-pending`。命令将仍为 PENDING 的演示告警的 `created_at` 和 `notified_at` 设置为当前时间前 1～50 秒。同批告警仍在窗口内时重复执行会更新 0 条。已处置告警及其他业务数据保留原值。

设置 `TEST_DATABASE_URL` 后运行 `python -m pytest -q` 可执行数据库集成测试。测试账号需要在测试库创建 schema 的权限，每个测试使用独立 schema 并在结束时清理。未配置该变量时 pytest 会跳过数据库集成测试。若需手工演练回滚，先将 `DATABASE_URL` 指向一次性验收库，再运行 `python -m alembic downgrade base`，该命令会删除 12 张业务表及其数据。

## 认证与权限（M3）

将生成的 `JWT_SECRET` 保存在本地 `.env` 或部署环境中，以便重启后继续验证同一批令牌。访问受保护接口时发送 `Authorization: Bearer <accessToken>`。刷新接口接收 `refreshToken`，返回新的令牌对。登出使用访问令牌，同时撤销它对应的刷新令牌。

Redis 离线时，`/health` 显示 `redis=down`，认证仍验证签名、有效期和账号状态。该期间跳过登录锁定及令牌黑名单，日志记录 `auth_redis_degraded`。设置 `TEST_REDIS_URL` 和 `TEST_DATABASE_URL` 后可验证 Redis 在线时的登录锁定、刷新轮换和登出撤销。

## 容器运行

```powershell
docker build -t silver-bell-backend:m1 .
docker run --rm --env-file .env -p 8000:8000 silver-bell-backend:m1
```

镜像以非 root 用户启动。容器中的连接地址应使用依赖服务的网络名称，连接 Windows 宿主机可使用 `host.docker.internal`。如果修改 `APP_PORT`，端口映射右侧也要改为相同值。

## 告警升级与通知（M6）

服务在启动时加载 `config/escalate.yaml`。每行的 `after_sec` 都从同一个 `notified_at` 起算。P0 建单时向启用的主联系人发 PUSH、SMS。第 60 秒转给老人绑定的网格员，第 120 秒转给本社区管理员，第 180 秒再次提醒该管理员。P1 在第 300 秒提醒主联系人。P2 的规则适用于已有告警，M5 ingest 对 P2 只记录事件。

本地在启动服务前设置以下变量，P0 的三个累计时点会缩短到 5、10、15 秒，扫描周期缩短到 0.1 秒。默认倍率为 1，默认每 2 秒扫描一次。

```powershell
$env:ESCALATE_TIME_SCALE = '0.08333333333333333'
$env:ESCALATE_POLL_INTERVAL_SEC = '0.1'
```

可用 `ESCALATE_CONFIG_PATH` 指定 YAML 文件。进程内调用 `app.state.escalation.rules.reload()` 重新读取文件，校验失败时保留上次成功的配置。Redis 在线时，扫描器在启动或重载后根据数据库中的未处置告警补排下一级。Redis 离线时，已在内存中排队的任务到期时会重新校验截止时间，缩短窗口的验收请先改配置再造告警。

Redis 使用 ZSET `alarm:escalate` 跨 API 重启保留任务。Redis 不可用时，扫描器记录 `alarm_escalation_redis_degraded` 警告并使用进程内 `asyncio.PriorityQueue`。**服务重启会丢失尚在内存中的任务**。Redis 恢复连接后，扫描器把内存中仍在等待的任务写回 ZSET。独立运行的 ingest 生产者和扫描器若需在 Redis 离线时协作，须共享同一个进程内的 `EscalationEngine`。

`NOTIFY_PROVIDER=mock` 是默认值，PUSH、SMS、CALL 记录 mock 日志。选 `aliyun` 可走供应商骨架，M6 骨架记录警告后调用 mock。INBOX 写入 M2 的 notification 表，WS 调用 M7 占位函数并返回失败。每个渠道独立发送、重试和写流水，重试间隔为 2 秒、5 秒。NOTIFY 流水的 `detail.attempts` 表示实际尝试次数。任一渠道失败均保留已提交的告警。
