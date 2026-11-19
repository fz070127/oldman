import json
import re
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.api.v1.router import router
from app.core.config import Settings
from app.core.exceptions import BizException
from app.main import create_app


@pytest.fixture
async def service(unused_tcp_port):
    settings = Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://localhost/test",
        redis_url="redis://localhost/0",
        mqtt_port=unused_tcp_port,
        cors_origins=["http://localhost:5173"],
    )
    app = create_app(settings)

    # 异常探针只挂在测试实例上。
    @app.get("/_test/error")
    async def error(value: int):
        if value == 0:
            raise BizException(1005, "状态冲突")
        raise RuntimeError("测试异常")

    transport = httpx.ASGITransport(app=app)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=transport, base_url="http://test") as client,
    ):
        yield app, client


@pytest.mark.parametrize("db_up", [True, False])
@pytest.mark.parametrize("redis_up", [True, False])
@pytest.mark.parametrize("mqtt_up", [True, False])
async def test_health(service, db_up, redis_up, mqtt_up):
    app, client = service
    connection = AsyncMock()
    pool = MagicMock()
    pool.connect.return_value.__aenter__.return_value = connection
    if not db_up:
        connection.execute.side_effect = ConnectionRefusedError()
    app.state.db = pool
    app.state.redis = AsyncMock()
    app.state.redis.ping.return_value = True
    if not redis_up:
        app.state.redis.ping.side_effect = ConnectionRefusedError()
    app.state.mqtt = MagicMock(connected=mqtt_up)

    response = await client.get("/health")
    trace = response.headers["X-Trace-Id"]
    assert response.status_code == 200
    assert re.fullmatch(r"[0-9a-f]{12}", trace)
    assert response.json() == {
        "code": 0,
        "message": "ok",
        "data": {
            "status": "up",
            "db": "up" if db_up else "down",
            "redis": "up" if redis_up else "down",
            "mqtt": "up" if mqtt_up else "down",
        },
        "traceId": trace,
    }
    assert str(connection.execute.await_args.args[0]) == "SELECT 1"
    app.state.redis.ping.assert_awaited_once()


@pytest.mark.parametrize(
    ("path", "status", "code", "message"),
    [
        ("/api/v1/missing", 200, 1004, "资源不存在"),
        ("/_test/error?value=x", 200, 1001, "参数校验失败"),
        ("/_test/error?value=0", 200, 1005, "状态冲突"),
        ("/_test/error?value=1", 500, 5000, "服务器内部错误"),
    ],
)
async def test_errors(service, path, status, code, message, capsys):
    _, client = service
    response = await client.get(path, headers={"Origin": "http://localhost:5173"})
    payload = response.json()
    trace = response.headers["X-Trace-Id"]
    assert response.status_code == status
    assert re.fullmatch(r"[0-9a-f]{12}", trace)
    assert payload == {"code": code, "message": payload["message"], "data": None, "traceId": trace}
    assert payload["message"].startswith(message)
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    if status == 500:
        entries = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
        entry = next(item for item in entries if item.get("traceId") == trace)
        assert entry["level"] == "error"
        assert entry["traceId"] == trace
        assert "Traceback" in entry["exception"] and "RuntimeError" in entry["exception"]


async def test_docs_and_router(service):
    _, client = service
    docs = await client.get("/docs")
    schema = await client.get("/openapi.json")
    assert docs.status_code == schema.status_code == 200
    assert docs.headers["X-Trace-Id"] != schema.headers["X-Trace-Id"]
    assert "/health" in schema.json()["paths"]
    assert router.prefix == "/api/v1"
