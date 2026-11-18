import asyncio
import os
from datetime import UTC, date, datetime
from typing import Annotated
from uuid import uuid4

import bcrypt
import httpx
import pytest
from fastapi import Depends
from jose import jwt
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.sql import ColumnElement

from app.core.config import Settings
from app.core.deps import get_user_scope, require_permission
from app.main import create_app
from app.models import AuditLog, Base, Community, Elder, FamilyBinding, Guardian, Role, User
from app.services.audit_service import AuditService

ROLES = {
    "ADMIN": (["*"], ["dashboard", "elder", "device", "event", "alarm", "screen", "system"]),
    "COMMUNITY_ADMIN": (
        ["elder:read", "elder:write", "device:*", "event:*", "alarm:*", "dashboard:*"],
        ["dashboard", "elder", "device", "event", "alarm", "screen"],
    ),
    "GUARDIAN": (
        ["elder:read", "event:read", "alarm:read", "alarm:ack", "alarm:dispatch"],
        ["dashboard", "elder", "alarm", "event"],
    ),
    "FAMILY": (["family:read", "alarm:ack"], ["family"]),
    "VIEWER": (["dashboard:read"], ["dashboard", "screen"]),
}
SECRET = "test-only-jwt-signing-key-for-the-m3-test-suite"


@pytest.fixture
async def sessions():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to run the authentication integration tests")
    schema = f"test_m3_{uuid4().hex}"
    admin_engine = create_async_engine(url)
    engine = create_async_engine(url, connect_args={"server_settings": {"search_path": schema}})
    try:
        async with admin_engine.begin() as connection:
            await connection.execute(text(f"CREATE SCHEMA {schema}"))
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        password_hash = bcrypt.hashpw(b"123456", bcrypt.gensalt(rounds=4)).decode()
        async with factory.begin() as db:
            db.add_all(Role(id=role, code=role, name=role) for role in ROLES)
            db.add_all(Community(id=cid, name=cid, address="测试") for cid in ("C01", "C02"))
            await db.flush()
            db.add_all(
                User(
                    id=role,
                    username=f"{schema}-{role}",
                    nickname=role,
                    role_code=role,
                    community_id=None if role == "ADMIN" else "C01",
                    password_hash=password_hash,
                )
                for role in ROLES
            )
            await db.flush()
            db.add_all(
                [
                    Guardian(id="G01", user_id="GUARDIAN", community_id="C01", name="G", phone="0"),
                    User(
                        id="disabled",
                        username="disabled",
                        nickname="关闭",
                        role_code="VIEWER",
                        password_hash=password_hash,
                        status=0,
                    ),
                ]
            )
            await db.flush()
            db.add_all(
                Elder(
                    id=eid,
                    name=eid,
                    gender=1,
                    birth_date=date(1950, 1, 1),
                    community_id=cid,
                    guardian_id=gid,
                    address="测试",
                )
                for eid, cid, gid in [
                    ("E1", "C01", "G01"),
                    ("E2", "C01", None),
                    ("E3", "C02", None),
                ]
            )
            await db.flush()
            db.add(FamilyBinding(id="B1", user_id="FAMILY", elder_id="E2", relation="子女"))
        yield factory, schema
    finally:
        await engine.dispose()
        async with admin_engine.begin() as connection:
            await connection.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        await admin_engine.dispose()


@pytest.fixture
async def auth_app(sessions, request):
    mode = getattr(request, "param", "down")
    redis_url = os.getenv("TEST_REDIS_URL") if mode == "up" else "redis://127.0.0.1:1/0"
    if not redis_url:
        pytest.skip("Set TEST_REDIS_URL to run the online Redis authentication test")
    settings = Settings(_env_file=None, jwt_secret=SECRET, redis_url=redis_url)
    app = create_app(settings)
    factory, schema = sessions

    @app.get("/write-test", dependencies=[Depends(require_permission("elder:write"))])
    async def write_test():
        return {"code": 0}

    @app.get("/device-test", dependencies=[Depends(require_permission("device:read"))])
    async def device_test():
        return {"code": 0}

    @app.get("/scope-test")
    async def scope_test(scope: Annotated[ColumnElement[bool] | None, Depends(get_user_scope)]):
        query = select(Elder.id).order_by(Elder.id)
        async with factory() as db:
            return list(await db.scalars(query if scope is None else query.where(scope)))

    transport = httpx.ASGITransport(app=app)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=transport, base_url="http://test") as client,
    ):
        app.state.db = factory.kw["bind"]
        yield app, client, schema


async def login(client, username, password="123456"):
    return (
        await client.post("/api/v1/auth/login", json={"username": username, "password": password})
    ).json()


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


async def test_role_menus_permissions_and_scopes(auth_app, capsys):
    _, client, schema = auth_app
    ids = {
        "ADMIN": ["E1", "E2", "E3"],
        "COMMUNITY_ADMIN": ["E1", "E2"],
        "GUARDIAN": ["E1"],
        "FAMILY": ["E2"],
        "VIEWER": ["E1", "E2"],
    }
    assert (await client.get("/health")).json()["data"] == {
        "status": "up",
        "db": "up",
        "redis": "down",
    }
    for role, (permissions, menus) in ROLES.items():
        username = f"{schema}-{role}"
        payload = await login(client, username)
        assert payload["code"] == 0
        assert len(payload["traceId"]) == 12
        result = payload["data"]
        assert result["user"] == {
            "id": role,
            "username": username,
            "nickname": role,
            "roleCode": role,
            "avatar": "",
            "communityId": "" if role == "ADMIN" else "C01",
            "permissions": permissions,
            "menus": menus,
        }
        headers = bearer(result["accessToken"])
        assert (await client.get("/api/v1/auth/me", headers=headers)).json()["data"] == result[
            "user"
        ]
        assert (await client.get("/scope-test", headers=headers)).json() == ids[role]
        write = await client.get("/write-test", headers=headers)
        assert write.status_code == 200
        assert write.json()["code"] == (0 if role in ("ADMIN", "COMMUNITY_ADMIN") else 1003)
        device = await client.get("/device-test", headers=headers)
        assert device.json()["code"] == (0 if role in ("ADMIN", "COMMUNITY_ADMIN") else 1003)
    assert '"event": "auth_redis_degraded"' in capsys.readouterr().out


async def test_invalid_tokens_and_input(auth_app):
    _, client, schema = auth_app
    result = (await login(client, f"{schema}-ADMIN"))["data"]
    access = jwt.decode(result["accessToken"], SECRET, algorithms=["HS256"])
    refresh = jwt.decode(result["refreshToken"], SECRET, algorithms=["HS256"])
    assert result["expiresIn"] == 1800
    assert refresh["exp"] - access["exp"] == 7 * 86400 - 1800
    assert refresh["jti"] != access["jti"]
    expired = jwt.encode({**access, "exp": int(datetime.now(UTC).timestamp()) - 1}, SECRET)
    for headers in ({}, bearer("invalid"), bearer(expired), bearer(result["refreshToken"])):
        response = await client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 200 and response.json()["code"] == 1002
    response = await client.post(
        "/api/v1/auth/refresh", json={"refreshToken": result["accessToken"]}
    )
    assert response.json()["code"] == 1002
    assert (await login(client, "disabled"))["code"] == 1002
    assert (await login(client, f"{schema}-ADMIN", "密" * 25))["code"] == 1001


async def test_password_audit_and_offline_login_limit(auth_app, sessions):
    _, client, schema = auth_app
    factory, _ = sessions
    username = f"{schema}-FAMILY"
    for _ in range(6):
        assert (await login(client, username, "wrong"))["code"] == 1002
    tokens = (await login(client, username))["data"]
    headers = bearer(tokens["accessToken"])
    response = await client.put(
        "/api/v1/auth/password",
        headers=headers,
        json={"oldPassword": "123456", "newPassword": "new-演示密码"},
    )
    assert response.json()["code"] == 0
    assert (await login(client, username, "new-演示密码"))["code"] == 0
    assert (await login(client, username))["code"] == 1002
    assert (await client.post("/api/v1/auth/logout", headers=headers)).json()["code"] == 0
    assert (await client.get("/api/v1/auth/me", headers=headers)).json()["code"] == 0
    response = await client.post(
        "/api/v1/auth/refresh", json={"refreshToken": tokens["refreshToken"]}
    )
    assert response.json()["code"] == 0
    async with factory() as db:
        user = await db.get(User, "FAMILY")
        assert user.last_login_at is not None
        entries = list(await db.scalars(select(AuditLog).order_by(AuditLog.created_at)))
        assert [entry.action for entry in entries] == [
            "LOGIN",
            "CHANGE_PASSWORD",
            "LOGIN",
            "LOGOUT",
        ]
        assert all(e.actor_id == e.target == "FAMILY" and e.detail == {} for e in entries)


async def test_audit_rollback_and_audit_insert_failure(auth_app, sessions, capsys):
    _, client, schema = auth_app
    factory, _ = sessions
    async with factory() as db:
        user = await db.get(User, "ADMIN")
        user.nickname = "将回滚"
        await db.flush()
        await AuditService(factory).log("ADMIN", "TEST", "ADMIN", {"test": True})
        await db.rollback()
    async with factory.begin() as db:
        assert (await db.get(User, "ADMIN")).nickname == "ADMIN"
        assert (await db.scalar(select(AuditLog))).detail == {"test": True}
        await db.execute(text("DROP TABLE audit_log"))
    assert (await login(client, f"{schema}-ADMIN"))["code"] == 0
    assert '"event": "audit_write_failed"' in capsys.readouterr().out


@pytest.mark.parametrize("auth_app", ["up"], indirect=True)
async def test_redis_login_lock_rotation_and_logout(auth_app):
    app, client, schema = auth_app
    redis = app.state.redis
    username = f"{schema}-ADMIN"
    key = f"login:fail:{username}"
    assert (await login(client, username, "wrong"))["code"] == 1002
    assert await redis.get(key) == b"1"
    assert (await login(client, username))["code"] == 0
    assert not await redis.exists(key)

    tokens = (await login(client, f"{schema}-GUARDIAN"))["data"]
    refresh = jwt.get_unverified_claims(tokens["refreshToken"])
    key_prefix = "auth:blacklist:"

    async def rotate():
        response = await client.post(
            "/api/v1/auth/refresh", json={"refreshToken": tokens["refreshToken"]}
        )
        return response.json()

    results = await asyncio.gather(rotate(), rotate())
    assert {result["code"] for result in results} == {0, 1002}
    new_tokens = next(result["data"] for result in results if result["code"] == 0)
    assert new_tokens["refreshToken"] != tokens["refreshToken"]
    remaining = refresh["exp"] - int(datetime.now(UTC).timestamp())
    assert abs(await redis.ttl(key_prefix + refresh["jti"]) - remaining) <= 1

    access_headers = bearer(new_tokens["accessToken"])
    assert (await client.post("/api/v1/auth/logout", headers=access_headers)).json()["code"] == 0
    assert (await client.get("/api/v1/auth/me", headers=access_headers)).json()["code"] == 1002
    logout_refresh = await client.post(
        "/api/v1/auth/refresh", json={"refreshToken": new_tokens["refreshToken"]}
    )
    assert logout_refresh.json()["code"] == 1002

    for _ in range(5):
        assert (await login(client, username, "wrong"))["code"] == 1002
    locked = await login(client, username)
    assert locked["code"] == 1006 and "10 分钟" in locked["message"]
    assert 590 <= await redis.ttl(key) <= 600
    await redis.delete(key)
