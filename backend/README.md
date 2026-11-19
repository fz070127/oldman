# 银铃守护 API

需要 Python 3.11–3.12、PostgreSQL 16、Redis 7。下列步骤从仓库根目录开始。Docker 可用于启动本地依赖，也可以使用已安装的 PostgreSQL 和 Redis。MQTT broker 用于设备上报与指令联调。

## 三步启动

### 1. 复制 .env 并安装依赖

Linux / macOS

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
cp .env.example .env
```

Windows PowerShell

```powershell
Set-Location backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

用 `python -c "import secrets; print(secrets.token_urlsafe(32))"` 生成随机值，分别填写 `JWT_SECRET`、`DEMO_SEED_PASSWORD` 以及下方命令用的 PostgreSQL 开发密码。已有开发库时，按实际连接信息填写 `DATABASE_URL` 和 `REDIS_URL`。首次填充将 `DEMO_SEED_PASSWORD` 用作演示账号密码。

### 2. 启动 PostgreSQL 和 Redis

使用 Docker 时，将下方两处 `<数据库密码>` 替换为同一个生成值。`token_urlsafe` 生成的密码可直接放在连接串内。

```text
docker network create silver-bell-m9
docker run -d --name silver-bell-db --network silver-bell-m9 -p 127.0.0.1:5432:5432 -e POSTGRES_DB=silver_bell -e "POSTGRES_PASSWORD=<数据库密码>" postgres:16
docker run -d --name silver-bell-redis --network silver-bell-m9 -p 127.0.0.1:6379:6379 redis:7
docker exec silver-bell-db pg_isready -h 127.0.0.1 -U postgres -d silver_bell
docker exec silver-bell-redis redis-cli ping
```

在 `.env` 中填入 `DATABASE_URL=postgresql+asyncpg://postgres:<数据库密码>@127.0.0.1:5432/silver_bell`。若使用原生依赖，先建开发库 `silver_bell` 并确认 PostgreSQL 和 Redis 都在监听。启动过上述容器后，下次可以直接用 `docker start silver-bell-db silver-bell-redis`。

### 3. 迁移、填充并启动 Uvicorn

```bash
python -m alembic upgrade head
python -m app.db.seed
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

**Windows 的 Uvicorn 命令必须使用 `--loop asyncio:SelectorEventLoop`**。Windows 默认的 Proactor 事件循环缺少 aiomqtt 用于注册套接字读事件的 `add_reader()`，会抛出 `NotImplementedError`。Uvicorn CLI 会在导入应用之前选择事件循环，因此 CLI 命令需要显式指定 Selector。若激活脚本被 PowerShell 策略限制，将命令中的 `python` 换成 `.\.venv\Scripts\python.exe`。

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --loop asyncio:SelectorEventLoop
```

打开 [Swagger UI](http://127.0.0.1:8000/docs) 查看请求和响应 schema，业务路由位于 `/api/v1`。`GET /health` 返回 HTTP 200，并报告 `db`、`redis`、`mqtt` 的 `up` 或 `down`。WebSocket 通过 `/api/v1/ws` 连接。HTTP 和 WebSocket 的业务时间戳输出北京时间 ISO 8601 `+08:00`，出生日期和趋势日期使用 `YYYY-MM-DD`。

## 演示步骤

**演示前先跑 `python -m app.db.seed --refresh-demo`。**

1. 首次在空库运行 `python -m app.db.seed`，新增 500 条告警、100 位老人和 90 台设备。第二次 seed 新增 0 条告警。演示账号包括 `admin`、`guardian01`、`family01` 和 `community01`，密码取首次填充时的 `DEMO_SEED_PASSWORD`。
2. 刷新使 `D001–D085` 上线，并将其心跳更新到近 10 秒内。`D086–D090` 置为离线，心跳约为 3 小时前。刷新原始 25 条演示 PENDING 告警中仍处于 PENDING 状态的记录，`--refresh-pending` 是兼容别名。
3. 刷新后立即打开大屏或刷新页面。没有设备持续上报心跳时，90 秒心跳阈值仍然生效，演示超过阈值时可再次执行刷新命令。短时间内连跑两次可看到更新数量归零。如果演示需展示最初的 25 条 PENDING，使用新填充的开发库，并在自动升级前启动演示。

## 环境变量

配置文件为 `backend/.env`，系统环境变量优先。含凭证的值由本机生成或由部署环境提供。

| 变量 | 用途 | 示例 |
| --- | --- | --- |
| `APP_ENV` | 运行环境，`prod` 关闭模拟事件接口并为 MQTT 启用 TLS | `development` |
| `APP_PORT` | `python -m app.main` 和镜像健康检查的端口，Uvicorn CLI 使用 `--port` | `8000` |
| `DATABASE_URL` | 异步 PostgreSQL 连接串 | `postgresql+asyncpg://postgres:<数据库密码>@127.0.0.1:5432/silver_bell` |
| `REDIS_URL` | Redis 连接串及逻辑库号 | `redis://127.0.0.1:6379/0` |
| `JWT_SECRET` | 访问和刷新令牌的签名密钥 | 本地生成的 32 字节随机值 |
| `DEMO_SEED_PASSWORD` | 首次填充时的演示账号密码，1–72 个 UTF-8 字节 | 本地生成的随机值 |
| `JWT_ALG` | JWT 签名算法 | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MIN` | 访问令牌有效期，分钟 | `30` |
| `REFRESH_TOKEN_EXPIRE_DAY` | 刷新令牌有效期，天 | `7` |
| `MINIO_ENDPOINT` | 对象存储地址，媒体存储预留配置 | `127.0.0.1:9000` |
| `MINIO_AK` | 对象存储访问标识 | 留空，接入时注入 |
| `MINIO_SK` | 对象存储访问密钥 | 留空，接入时注入 |
| `MINIO_BUCKET` | 对象存储桶 | `silver-bell` |
| `MQTT_HOST` | MQTT broker 主机 | `127.0.0.1` |
| `MQTT_PORT` | MQTT broker 端口 | `1883`，生产通常用 `8883` |
| `MQTT_USER` | MQTT 用户名 | 留空，或使用 broker 分配的用户名 |
| `MQTT_PASS` | MQTT 密码 | 留空，或由 broker 部署环境注入 |
| `NOTIFY_PROVIDER` | 外部通知渠道配置 | `mock`，`aliyun` 选用供应商接入骨架 |
| `ESCALATE_CONFIG_PATH` | 告警升级规则文件，默认取随项目安装的规则 | `config/escalate.yaml` |
| `ESCALATE_TIME_SCALE` | 告警升级时间倍率 | `1` |
| `ESCALATE_POLL_INTERVAL_SEC` | 告警扫描间隔，秒 | `2` |
| `CORS_ORIGINS` | 允许的前端 Origin，JSON 字符串数组 | `["http://localhost:5173"]` |
| `TEST_DATABASE_URL` | pytest 使用的独立 PostgreSQL 库 | `postgresql+asyncpg://postgres:<数据库密码>@127.0.0.1:5432/silver_bell_test` |
| `TEST_REDIS_URL` | pytest 使用的独立 Redis 实例或逻辑库 | `redis://127.0.0.1:6379/15` |
| `LOADTEST_TOKEN` | 压测脚本使用的访问令牌 | `/api/v1/auth/login` 返回的 `data.accessToken` |

## 常见问题

- **连不上数据库**。检查 `/health` 的 `db`，核对数据库名称、端口、密码和 `postgresql+asyncpg://` 前缀。连接成功但报表不存在时执行 `python -m alembic upgrade head`。
- **MQTT 连不上**。检查 broker 是否在监听配置的地址及端口。`APP_ENV=prod` 使用 TLS，证书链必须能被系统信任。Windows 确认使用 Selector。未启动 broker 时 `/health` 显示 `mqtt=down`，本地仍可使用 HTTP 业务接口。
- **端口占用**。Windows 用 `Get-NetTCPConnection -LocalPort 8000` 查监听进程，Linux 可用 `ss -ltnp 'sport = :8000'`。更换后端端口时同步更新前端和压测脚本的 API 地址。容器内端口由 `APP_PORT` 控制，并与 `-p` 的容器端口保持一致。
- **中文乱码**。`.env` 和 PostgreSQL 数据库使用 UTF-8。PowerShell 中可设置 `$env:PYTHONUTF8 = '1'`，查看 UTF-8 日志时使用 `Get-Content -Encoding utf8`。

## 容器运行

完整部署编排见 [deploy/README.md](../deploy/README.md)。

在 `backend` 下构建，通过第 2 步的 Docker 网络连接依赖。将下方数据库密码替换为相同开发密码。容器以非 root 用户运行，入口脚本迁移到 Alembic head 后启动 Uvicorn。Linux 的 `app.main` 使用默认事件循环选择，跳过 Windows Selector 分支。

```text
docker build -t silver-bell-backend:m9 .
docker image inspect silver-bell-backend:m9 --format "{{.Size}}"
docker run -d --name silver-bell-api --network silver-bell-m9 --env-file .env -e "DATABASE_URL=postgresql+asyncpg://postgres:<数据库密码>@silver-bell-db:5432/silver_bell" -e "REDIS_URL=redis://silver-bell-redis:6379/0" -p 127.0.0.1:8000:8000 silver-bell-backend:m9
docker inspect silver-bell-api --format "{{.State.Health.Status}}"
docker exec silver-bell-api id -u
docker exec silver-bell-api curl -fsS http://127.0.0.1:8000/health
docker exec silver-bell-api python -m app.db.seed
```

## 测试、覆盖率和压测

在 `backend` 下运行，先创建独立的 PostgreSQL 测试库。测试账号需要创建 schema 的权限。设置表中的 `TEST_DATABASE_URL` 和 `TEST_REDIS_URL` 后执行完整套件，未配置时依赖对应服务的测试会跳过。

```text
python -m pytest --cov --cov-report=term-missing
ruff check . ../scripts
ruff format --check . ../scripts
```

压测前启动服务并填充数据，通过 Swagger 的 `POST /api/v1/auth/login` 获取管理员的 `data.accessToken`，将其设为当前终端的 `LOADTEST_TOKEN`，在 `backend` 下运行：

```text
python ../scripts/loadtest.py --base-url http://127.0.0.1:8000/api/v1
```

脚本以 50 并发依次请求 `GET /alarms`、`GET /events` 各 30 秒，使用默认分页 `page=1&pageSize=20`。QPS 包括所有尝试，P50、P95、P99 取成功请求的 HTTP 往返延迟。错误率计入 HTTP、传输、JSON 和业务码错误。任一路径 P95 达到 300 ms 或存在错误，脚本退出码为 1。

### M9 实测（2026-11-19）

在 Windows 上使用 Python 3.12.5、PostgreSQL 16.2 和 Redis 7.4.11。64 项测试全部通过。覆盖率统计 `app` 的语句覆盖率，完整测试使用独立数据库和 Redis 逻辑库。

| 模块 | 已覆盖 / 总语句 | 覆盖率 |
| --- | ---: | ---: |
| `app/api` | 289 / 349 | 82.81% |
| `app/core` | 205 / 211 | 97.16% |
| `app/db` | 161 / 175 | 92.00% |
| `app/main.py` | 99 / 101 | 98.02% |
| `app/models` | 278 / 278 | 100.00% |
| `app/mqtt` | 148 / 230 | 64.35% |
| `app/schemas` | 395 / 397 | 99.50% |
| `app/services` | 885 / 1,023 | 86.51% |
| `app/ws` | 103 / 110 | 93.64% |
| **合计** | **2,563 / 2,874** | **89.18%** |

本机 Uvicorn 单进程，客户端走回环 HTTP，使用管理员令牌和 500 条事件、500 条告警的演示库。MQTT 未接 broker。以下为每个端点 50 并发、各发起 30 秒请求的结果。

| 接口 | 请求数 | QPS | P50 | P95 | P99 | 错误率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `GET /api/v1/alarms` | 3,807 | 125.80 | 276.12 ms | 1111.90 ms | 1740.31 ms | 0.00% |
| `GET /api/v1/events` | 3,976 | 131.26 | 266.07 ms | 1087.79 ms | 1684.63 ms | 0.00% |

两个接口的 P95 均超过 300 ms。原生 `/health` 返回 HTTP 200，PostgreSQL 和 Redis 均为 `up`。大屏接口从 0 台在线恢复为 85 台在线、5 台离线，返回 `onlineRate=0.94`。连续第二次刷新更新 0 条。一轮隔离库回归覆盖了初始 25 条 PENDING 告警的完整刷新。

### 未验证项

- Dockerfile 未执行构建。
- Compose 编排未实际启动。
- Docker 镜像大小未知。

## 认证与权限（M3）

将生成的 `JWT_SECRET` 保存在本地 `.env` 或部署环境中，以便重启后继续验证同一批令牌。访问受保护接口时发送 `Authorization: Bearer <accessToken>`。刷新接口接收 `refreshToken`，返回新的令牌对。登出使用访问令牌，同时撤销它对应的刷新令牌。

Redis 离线时，`/health` 显示 `redis=down`，认证仍验证签名、有效期和账号状态。该期间跳过登录锁定及令牌黑名单，日志记录 `auth_redis_degraded`。设置 `TEST_REDIS_URL` 和 `TEST_DATABASE_URL` 后可验证 Redis 在线时的登录锁定、刷新轮换和登出撤销。

媒体接口返回已存储的 URL，`expiresInSec=0` 表示该接口未签发临时 URL。

## MQTT 设备接入（M8）

运行 `python -m alembic upgrade head` 创建指令日志表。设置 `MQTT_HOST`、`MQTT_PORT`、`MQTT_USER` 和 `MQTT_PASS` 连接 broker。本地默认使用 1883。生产环境设置 `APP_ENV=prod`、`MQTT_PORT=8883`，并在系统信任库配置 broker 的 TLS 证书颁发机构。Windows 上，aiomqtt 使用 Selector 事件循环，直接运行 `python -m app.main` 时会自动选择。

`POST /api/v1/devices/{id}/reboot` 下发 `restart`，收到成功回执后返回 `code=0`。无回执时默认等待 5 秒。同一设备的同名指令一次只允许等待一条。回执通过当前 API 进程内的 Future 交付，部署时使用单 worker。

## 告警升级与通知（M6）

服务在启动时加载 `config/escalate.yaml`。每行的 `after_sec` 都从同一个 `notified_at` 起算。P0 建单时向启用的主联系人发 PUSH、SMS。第 60 秒转给老人绑定的网格员，第 120 秒转给本社区管理员，第 180 秒再次提醒该管理员。P1 在第 300 秒提醒主联系人。P2 的规则适用于已有告警，M5 ingest 对 P2 只记录事件。

本地在启动服务前设置以下变量，P0 的三个累计时点会缩短到 5、10、15 秒，扫描周期缩短到 0.1 秒。默认倍率为 1，默认每 2 秒扫描一次。

```powershell
$env:ESCALATE_TIME_SCALE = '0.08333333333333333'
$env:ESCALATE_POLL_INTERVAL_SEC = '0.1'
```

可用 `ESCALATE_CONFIG_PATH` 指定 YAML 文件。进程内调用 `app.state.escalation.rules.reload()` 重新读取文件，校验失败时保留上次成功的配置。Redis 在线时，扫描器在启动或重载后根据数据库中的未处置告警补排下一级。Redis 离线时，已在内存中排队的任务到期时会重新校验截止时间，缩短窗口的验收请先改配置再造告警。

Redis 使用 ZSET `alarm:escalate` 跨 API 重启保留任务。Redis 不可用时，扫描器记录 `alarm_escalation_redis_degraded` 警告并使用进程内 `asyncio.PriorityQueue`。**服务重启会丢失尚在内存中的任务**。Redis 恢复连接后，扫描器把内存中仍在等待的任务写回 ZSET。独立运行的 ingest 生产者和扫描器若需在 Redis 离线时协作，须共享同一个进程内的 `EscalationEngine`。

`NOTIFY_PROVIDER=mock` 是默认值，PUSH、SMS、CALL 记录 mock 日志。选 `aliyun` 可走供应商骨架，M6 骨架记录警告后调用 mock。INBOX 写入 M2 的 notification 表，WS 向目标用户已连接的 WebSocket 投递。每个渠道独立发送、重试和写流水，重试间隔为 2 秒、5 秒。NOTIFY 流水的 `detail.attempts` 表示实际尝试次数。任一渠道失败均保留已提交的告警。

## WebSocket 与看板（M7）

- 使用 `ws://<host>/api/v1/ws?token=<accessToken>` 连接，每 30 秒发 `{"type":"PING"}`，收到 `{"type":"PONG"}`。无效访问令牌关闭码 `4401`，60 秒无消息关闭码 `4408`。重连后通过 `/api/v1/alarms/pending-count` 补数。
- `ALARM_NEW`、`ALARM_UPDATE` 按老人绑定关系和社区权限广播，`DEVICE_STATUS` 推给管理员及设备绑定社区的看板用户。WS 连接保存在进程内，演示使用单 worker。
- 设备上报心跳后上线；距最后一次心跳超过 90 秒后，由每 30 秒运行的扫描器置为离线并广播。断开 broker 不会立即让所有设备离线：正常情况下推送在最后心跳后的 90–120 秒内到达。
- `/api/v1/dashboard` 的五个接口要求 `dashboard:read`，社区用户仅查看本社区。趋势以北京时间按日聚合，`days` 取 1–90，默认 7，缺失日期补零；社区坐标是稳定的归一化演示坐标，不代表实际地理位置。
