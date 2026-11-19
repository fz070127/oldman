# 银铃守护部署

**未验证**。本次交付部署配置和脚本。Dockerfile 未执行构建，Compose 编排未实际启动，镜像大小未知。

## 一键启动

安装 Docker 和 Compose v2.17 或以上版本。在仓库根目录用 Bash 执行以下命令。首次启动需要拉取镜像，并构建后端和 Web 镜像。

```bash
cd deploy
cp .env.example .env
# 先在 .env 填写演示环境所需的凭据
bash scripts/init.sh
```

为 `POSTGRES_PASSWORD`、`MINIO_ROOT_PASSWORD`、`EMQX_DASHBOARD__DEFAULT_PASSWORD`、`JWT_SECRET` 和 `DEMO_SEED_PASSWORD` 分别生成凭据并填入 `.env`。可用 `python -c "import secrets; print(secrets.token_urlsafe(32))"` 生成随机值。

脚本等待 PostgreSQL 接受 TCP 连接。后端镜像入口执行 Alembic 迁移，随后填充演示数据，再启动后端、Web 管理端和大屏。启动后访问 `http://localhost:8080`，演示账号为 `admin`，密码取 `DEMO_SEED_PASSWORD`。演示前执行 `docker compose exec backend python -m app.db.seed --refresh-demo`。

如需家属端，在 `deploy/` 执行 `docker compose --profile h5 up -d --build h5`，然后访问 `http://localhost:8081`。当前 H5 的登录、告警和监护列表使用模拟数据。

## 服务端口

| 服务 | 宿主机端口 | 用途 |
| --- | --- | --- |
| `postgres` | `5432` | PostgreSQL 16，业务库和 Alembic 迁移 |
| `redis` | `6379` | Redis 7，运行状态和缓存 |
| `minio` | `9000`、`9001` | S3 对象存储 API、管理控制台 |
| `emqx` | `1883`、`18083` | EMQX 5 的 MQTT 与管理控制台 |
| `backend` | `8000` | FastAPI REST API、WebSocket、`/health` |
| `frontend` | `8080` | Nginx 托管 Web 管理端和大屏，转发 API 和 WebSocket |
| `h5` | `8081` | Nginx 托管家属端静态资源，按 `h5` profile 启用 |

默认仅 Web 和 H5 端口绑定到所有网卡，其余端口绑定到 `127.0.0.1`。容器间使用 Compose 服务名通信。局域网设备接入时，按部署环境配置 MQTT 监听地址和防火墙。`APP_PORT` 默认是 `8000`，如有修改，需同步更新 `nginx.conf` 的两处上游端口并重新构建 Web 镜像。

## 日志与健康状态

在 `deploy/` 执行以下命令。`backend` 可以替换成表中的任意服务名，查看 `h5` 日志时加上 `--profile h5`。

```bash
docker compose --profile h5 ps
docker compose logs -f --tail=100 backend
```

`http://localhost:8000/health` 的响应中可查看 PostgreSQL、Redis 和 MQTT 的连接状态。

## 重置演示环境

在 `deploy/` 执行 `bash scripts/reset.sh`。这会停止该 Compose 项目的容器（含已启用的 H5），**删除 `pg_data`、`minio_data` 和 `emqx_data` 中的全部数据**，并重新运行初始化。若需要 H5，重置后按上述命令再次启用。

## 生产部署注意事项

- 在 `.env` 中设置 `APP_ENV=prod`。后端在该模式下关闭 `POST /api/v1/events/mock`，并为 MQTT 启用 TLS。
- 更换 PostgreSQL 密码、EMQX 控制台密码和 `JWT_SECRET`。若数据库密码含 URL 保留字符，在 `DATABASE_URL` 中使用百分号编码的密码，`POSTGRES_PASSWORD` 仍填写原值。已有数据卷上的数据库和控制台密码需在对应服务内轮换。
- 更换 `MINIO_ROOT_USER` 和 `MINIO_ROOT_PASSWORD`。为应用配置只允许访问所需 bucket 的 MinIO 凭据，并将 `MINIO_AK` 和 `MINIO_SK` 设置为该凭据。
- 为 EMQX 或外部 broker 配置 MQTT TLS（通常为 `8883`）、可信证书、客户端身份验证和主题访问权限。同步更新 `MQTT_HOST`、`MQTT_PORT`、`MQTT_USER` 和 `MQTT_PASS`，并将边缘设备切换到 TLS 入口。客户端使用的 broker 主机名须匹配证书。
- 使用 HTTPS/WSS 作为网页入口，在 `CORS_ORIGINS` 中填写实际允许的来源。管理控制台和数据服务端口应限制在受信网络内。
- 生产初始化可用 `docker compose up -d backend frontend`，由后端入口执行迁移。演示用 `init.sh` 和 `reset.sh` 会填充样例数据，生产账号应按上线流程单独初始化。

## Windows

在 Windows 上用 Git Bash 或 WSL 运行这两份 Bash 脚本，并使用 Docker 的 Linux 容器模式。容器通过 `python -m app.main` 启动，使用 Linux 默认事件循环。

若在 Windows 本机直接使用 Uvicorn，从 `backend/` 执行 `python -m uvicorn app.main:app --reload --loop asyncio:SelectorEventLoop`，以兼容 MQTT 异步客户端。直接运行 `python -m app.main` 时，入口会自动为 Windows 选择对应的事件循环。
