import asyncio
import json
import os
from datetime import UTC, date, datetime, timedelta
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import Settings
from app.core.permissions import ROLE_PERMISSIONS
from app.core.tokens import TokenIssuer
from app.main import create_app
from app.models import (
    Alarm,
    AuditLog,
    Base,
    Community,
    Device,
    Elder,
    Event,
    FamilyBinding,
    Guardian,
    MqttCmdLog,
    Role,
    User,
)
from app.models.enums import RoleCode
from app.mqtt.handlers import MqttHandlers
from app.mqtt.publisher import MqttPublisher

ACCOUNTS = {
    "admin": (RoleCode.ADMIN, None),
    "community01": (RoleCode.COMMUNITY_ADMIN, "C001"),
    "guardian01": (RoleCode.GUARDIAN, "C001"),
    "guardian02": (RoleCode.GUARDIAN, "C002"),
    "family01": (RoleCode.FAMILY, "C001"),
    "viewer01": (RoleCode.VIEWER, "C001"),
}
ELDER_BODY = {
    "name": "新增验收老人",
    "gender": 2,
    "birthDate": "1948-03-02",
    "phone": "13812348888",
    "communityId": "C01",
    "guardianId": "G01",
    "address": "幸福里小区",
    "roomNo": "501",
    "healthTags": ["独居"],
    "detectMode": 3,
    "emergencyContact": [{"name": "王女士", "phone": "13912341111", "primary": True}],
}


async def seed_records(db):
    db.add_all(Role(id=code, code=code, name=code) for code in ROLE_PERMISSIONS)
    db.add_all(
        Community(id=cid, name=name, address=name)
        for cid, name in [("C001", "幸福里"), ("C002", "安康苑")]
    )
    await db.flush()
    db.add_all(
        User(
            id=uid,
            username=uid,
            role_code=role,
            community_id=cid,
            nickname=uid,
            password_hash="unused",
            phone="13912341111",
        )
        for uid, (role, cid) in ACCOUNTS.items()
    )
    await db.flush()
    db.add_all(
        Guardian(id=gid, community_id=cid, user_id=uid, name=gid, phone="13912341111")
        for gid, cid, uid in [("G001", "C001", "guardian01"), ("G002", "C002", "guardian02")]
    )
    await db.flush()
    db.add_all(
        Elder(
            id=eid,
            name=name,
            gender=2,
            birth_date=date(1948, 3, 2),
            phone="13812348888",
            community_id=cid,
            guardian_id=gid,
            address=address,
            room_no=room,
            status=status,
            emergency_contact=ELDER_BODY["emergencyContact"],
        )
        for eid, name, cid, gid, address, room, status in [
            ("E001", "王秀兰", "C001", "G001", "幸福里 3 栋", "301", 1),
            ("E002", "李桂芳", "C002", "G002", "安康苑 2 栋", "502", 1),
            ("E003", "暂停档案", "C001", "G001", "幸福里 7 栋", "701", 2),
            ("E004", "待装设备", "C001", "G001", "幸福里 8 栋", "420", 1),
            ("E005", "跨社区档案", "C002", "G002", "安康苑 6 栋", "602", 1),
        ]
    )
    await db.flush()
    db.add_all(
        [
            Device(
                id="D001",
                device_no="EDGE-001",
                elder_id="E001",
                type=1,
                status=1,
                install_addr="幸福里机柜",
                config={"roi": [[0.2, 0.3]], "quietHours": ["22:00-06:00"]},
            ),
            Device(id="D002", device_no="EDGE-002", elder_id="E002", type=1, status=2),
            Device(id="D003", device_no="EDGE-003", type=1),
            FamilyBinding(id="B001", elder_id="E001", user_id="family01", relation="子女"),
        ]
    )
    await db.flush()
    now = datetime.now(UTC)
    db.add_all(
        Event(
            id=f"EV{i}",
            event_id=f"event-{i}",
            device_id="D001",
            elder_id="E001",
            type="FALL",
            level="P1",
            confidence=0.8,
            occurred_at=now - timedelta(days=i),
        )
        for i in range(1, 7)
    )
    await db.flush()
    db.add_all(
        Alarm(
            id=f"A{i}",
            event_id=f"EV{i}",
            elder_id="E001",
            level="P1",
            status="PENDING",
            created_at=now - timedelta(days=days),
        )
        for i, days in [(1, 3), (2, 31)]
    )


@pytest.fixture
async def records_server(monkeypatch):
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to run records integration tests")
    schema = f"test_m4_{uuid4().hex}"
    admin_engine = create_async_engine(url)
    engine = create_async_engine(url, connect_args={"server_settings": {"search_path": schema}})
    redis_url = os.getenv("TEST_REDIS_URL")
    settings = Settings(
        _env_file=None,
        jwt_secret="test-only-signing-key-for-records",
        redis_url=redis_url or "redis://127.0.0.1:1/0",
    )
    app = create_app(settings)
    monkeypatch.setattr("app.main.create_async_engine", lambda _: engine)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    tokens = TokenIssuer(settings)
    headers = {
        uid: {"Authorization": f"Bearer {tokens.issue(uid)['accessToken']}"} for uid in ACCOUNTS
    }
    try:
        async with admin_engine.begin() as connection:
            await connection.execute(text(f"CREATE SCHEMA {schema}"))
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with factory.begin() as db:
            await seed_records(db)
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test/api/v1"
            ) as client,
        ):
            if not redis_url:
                # spec=Redis 会把 exists 变成同步 Mock（redis-py 用装饰器包装协程方法，
                # inspect.iscoroutinefunction 返回 False），await 时抛 TypeError。
                # 这里用无 spec 的 AsyncMock，再由测试显式设定各方法行为。
                app.state.redis = AsyncMock()
                app.state.redis.exists.return_value = 0
                # pipeline() 在 redis-py 里是同步方法，返回可作为 async 上下文管理器的对象。
                # AsyncMock 会把它变成协程，业务代码的 `async with` 会失败，所以用 Mock。
                pipeline = AsyncMock()
                pipeline.__aenter__.return_value = pipeline
                pipeline.__aexit__.return_value = False
                app.state.redis.pipeline = Mock(return_value=pipeline)
            yield app, client, headers, factory
    finally:
        await engine.dispose()
        async with admin_engine.begin() as connection:
            await connection.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        await admin_engine.dispose()


@pytest.fixture
async def records_app(records_server):
    _, client, headers, factory = records_server
    return client, headers, factory


async def test_system_management(records_app):
    client, headers, _ = records_app
    admin = headers["admin"]
    denied = await client.get("/system/users", headers=headers["guardian01"])
    assert denied.json()["code"] == 1003
    guardians = await client.get("/system/guardians", headers=admin, params={"communityId": "C01"})
    assert [item["id"] for item in guardians.json()["data"]["list"]] == ["G001"]

    created = await client.post(
        "/system/communities", headers=admin, json={"name": "测试社区", "address": "32 号"}
    )
    assert created.status_code == 201
    community = created.json()["data"]["id"]
    body = {
        "username": "temporary_user",
        "nickname": "测试用户",
        "roleCode": RoleCode.VIEWER,
        "communityId": community,
    }
    missing_password = await client.post("/system/users", headers=admin, json=body)
    assert missing_password.json()["code"] == 1001
    created = await client.post("/system/users", headers=admin, json={**body, "password": "test-local-123"})
    assert created.status_code == 201
    user = created.json()["data"]
    assert user["communityName"] == "测试社区" and "password" not in user

    updated = await client.put(f"/system/users/{user['id']}", headers=admin, json={"status": 2})
    assert updated.json()["data"]["status"] == 2
    users = await client.get("/system/users", headers=admin, params={"status": 2, "keyword": "temporary"})
    assert [item["id"] for item in users.json()["data"]["list"]] == [user["id"]]

    blocked = await client.delete(f"/system/communities/{community}", headers=admin)
    assert blocked.json()["code"] == 1005
    assert (await client.delete(f"/system/users/{user['id']}", headers=admin)).json()["code"] == 0
    assert (await client.delete(f"/system/communities/{community}", headers=admin)).json()["code"] == 0


async def test_mqtt_command_reply_and_timeout(records_server):
    app, _, _, factory = records_server
    mqtt = AsyncMock()
    publisher = MqttPublisher(mqtt, factory)
    handlers = MqttHandlers(factory, app.state.redis, publisher)

    async def reply_before_publish_returns(topic, message):
        assert topic == "edge/EDGE-001/cmd"
        assert json.loads(message) == {"cmd": "restart", "payload": {}}
        assert not await publisher.publish_cmd("EDGE-001", "restart", {})
        await handlers.on_cmd_reply("EDGE-002", b'{"cmd":"restart","ok":true}')
        await handlers.on_cmd_reply("EDGE-001", b'{"cmd":"restart","ok":"true"}')
        await handlers.on_cmd_reply("EDGE-001", b'{"cmd":"restart","ok":true,"msg":"done"}')

    mqtt.publish.side_effect = reply_before_publish_returns
    assert await publisher.publish_cmd("EDGE-001", "restart", {})
    mqtt.publish.side_effect = None
    assert not await publisher.publish_cmd("EDGE-001", "restart", {}, timeout=0.02)

    async with factory() as db:
        commands = list(await db.scalars(select(MqttCmdLog).order_by(MqttCmdLog.created_at)))
    assert [(command.status, command.reply_message) for command in commands] == [
        ("ACKNOWLEDGED", "done"),
        ("TIMEOUT", None),
    ]
    assert all(command.completed_at is not None for command in commands)
    assert not publisher.pending


def response_data(response, *, status=200, code=0):
    assert response.status_code == status
    payload = response.json()
    assert payload["code"] == code, payload
    assert payload["traceId"] == response.headers["X-Trace-Id"]
    return payload["data"]


async def test_elder_list_scope_and_detail(records_app):
    client, headers, _ = records_app
    admin = headers["admin"]
    first = response_data(await client.get("elders?pageSize=1", headers=admin))
    assert (first["total"], first["pageSize"], len(first["list"])) == (4, 1, 1)
    assert first["list"][0]["phone"] == "138****8888"
    assert first["list"][0]["deviceOnline"] is True
    assert first["list"][0]["alarmCount30d"] == 1
    assert first["list"][0]["communityName"] == "幸福里"
    assert first["list"][0]["guardianName"] == "G001"
    for query, ids in [
        ("keyword=王", ["E001"]),
        ("keyword=502", ["E002"]),
        ("keyword=8 栋", ["E004"]),
        ("keyword=%25", []),
        ("status=2", ["E003"]),
        ("communityId=C01&guardianId=G01", ["E001", "E004"]),
    ]:
        data = response_data(await client.get(f"elders?{query}", headers=admin))
        assert [elder["id"] for elder in data["list"]] == ids
    response_data(await client.get("elders?pageSize=101", headers=admin), code=1001)
    response_data(await client.get("elders"), code=1002)
    for uid in ("family01", "viewer01"):
        response_data(await client.get("elders", headers=headers[uid]), code=1003)
    guardian = headers["guardian01"]
    data = response_data(await client.get("elders", headers=guardian))
    assert [item["id"] for item in data["list"]] == ["E001", "E004"]
    response_data(await client.get("elders/E002", headers=guardian), code=1004)
    detail = response_data(await client.get("elders/E001", headers=admin))
    assert detail["phone"] == "13812348888"
    assert detail["emergencyContact"] == ELDER_BODY["emergencyContact"]
    assert detail["device"]["id"] == "D001"
    assert [item["id"] for item in detail["recentEvents"]] == [f"EV{i}" for i in range(1, 6)]
    assert detail["familyBindings"][0]["phone"] == "139****1111"
    assert (
        response_data(await client.get("elders/E001", headers=guardian))["phone"] == "138****8888"
    )


async def test_elder_mutations_bindings_and_audit(records_app):
    client, headers, factory = records_app
    admin, manager, guardian = (headers[uid] for uid in ("admin", "community01", "guardian01"))
    response_data(await client.post("elders", headers=guardian, json=ELDER_BODY), code=1003)
    for invalid in ({"name": " "}, {"gender": 3}, {"birthDate": "2999-01-01"}, {"phone": "100"}):
        response_data(
            await client.post("elders", headers=admin, json={**ELDER_BODY, **invalid}), code=1001
        )
    for missing in ({"communityId": "unknown"}, {"guardianId": "unknown"}):
        response_data(
            await client.post("elders", headers=admin, json={**ELDER_BODY, **missing}), code=1004
        )
    response_data(
        await client.post("elders", headers=manager, json={**ELDER_BODY, "communityId": "C002"}),
        code=1003,
    )
    response_data(
        await client.put("elders/E002", headers=manager, json={"name": "越权"}), code=1004
    )
    elder = response_data(await client.post("elders", headers=manager, json=ELDER_BODY), status=201)
    eid = elder["id"]
    assert (elder["communityId"], elder["guardianId"], elder["device"]) == ("C001", "G001", None)
    assert response_data(await client.get(f"elders/{eid}", headers=admin)) == elder
    response_data(
        await client.put(f"elders/{eid}", headers=manager, json={"communityId": "C002"}), code=1001
    )
    response_data(
        await client.put(f"elders/{eid}", headers=manager, json={"guardianId": "G002"}), code=1001
    )
    updated = response_data(
        await client.put(f"elders/{eid}", headers=manager, json={"name": "已改名"})
    )
    assert updated == {**elder, "name": "已改名"}
    body = {"userId": "family01", "relation": "子女", "isPrimary": True, "notifyOrder": 2}
    binding = response_data(
        await client.post(f"elders/{eid}/bindings", headers=manager, json=body), status=201
    )
    assert response_data(await client.get(f"elders/{eid}/bindings", headers=guardian)) == [binding]
    response_data(
        await client.post(f"elders/{eid}/bindings", headers=manager, json=body), code=1005
    )
    binding_id = binding["bindingId"]
    response_data(
        await client.delete(f"elders/E001/bindings/{binding_id}", headers=manager), code=1004
    )
    response_data(await client.delete(f"elders/{eid}/bindings/{binding_id}", headers=manager))
    assert response_data(await client.get(f"elders/{eid}/bindings", headers=manager)) == []
    assert response_data(await client.delete(f"elders/{eid}", headers=manager))["status"] == 2
    assert response_data(await client.get("elders?keyword=已改名", headers=manager))["total"] == 0
    paused = response_data(await client.get("elders?keyword=已改名&status=2", headers=manager))
    assert paused["list"][0]["id"] == eid
    assert response_data(await client.get(f"elders/{eid}", headers=manager))["status"] == 2
    async with factory() as db:
        audits = list(
            await db.scalars(
                select(AuditLog).where(AuditLog.target == eid).order_by(AuditLog.created_at)
            )
        )
        assert [row.action for row in audits] == [
            "CREATE_ELDER",
            "UPDATE_ELDER",
            "UPDATE_ELDER",
            "UPDATE_ELDER",
            "DELETE_ELDER",
        ]
        assert all(row.actor_id == "community01" for row in audits)
        assert audits[0].detail["phone"] == "138****8888"
        assert audits[0].detail["emergencyContact"][0]["phone"] == "139****1111"
        assert audits[1].detail == {"name": "已改名"}
        assert audits[2].detail["familyBinding"]["operation"] == "add"
        assert audits[3].detail["familyBinding"]["operation"] == "remove"


async def test_device_scope_config_and_uniqueness(records_server, monkeypatch):
    app, client, headers, factory = records_server
    admin, manager, guardian = (headers[uid] for uid in ("admin", "community01", "guardian01"))
    data = response_data(await client.get("devices", headers=admin))
    assert [item["id"] for item in data["list"]] == ["D001", "D002", "D003"]
    scoped = response_data(await client.get("devices", headers=manager))
    assert [item["id"] for item in scoped["list"]] == ["D001"]
    assert response_data(await client.get("devices?communityId=C02", headers=manager))["total"] == 0
    assert (
        response_data(await client.get("devices?keyword=机柜&status=1", headers=admin))["total"]
        == 1
    )
    response_data(await client.get("devices/D002", headers=manager), code=1004)
    response_data(await client.get("devices", headers=guardian), code=1003)
    with monkeypatch.context() as permissions:
        permissions.setitem(ROLE_PERMISSIONS, RoleCode.GUARDIAN, ("device:read",))
        scoped = response_data(await client.get("devices", headers=guardian))
        assert [item["id"] for item in scoped["list"]] == ["D001"]
    publisher = app.state.mqtt_publisher = AsyncMock()
    publisher.publish_cmd.side_effect = [False, True]
    response_data(await client.post("devices/D001/reboot", headers=manager), code=5001)
    response_data(await client.post("devices/D002/reboot", headers=manager), code=1004)
    response_data(await client.post("devices/D001/reboot", headers=manager))
    assert publisher.publish_cmd.await_count == 2
    publisher.publish_cmd.assert_awaited_with("EDGE-001", "restart", {})
    body = {"deviceNo": "NEW-001", "elderId": "E004", "type": 1, "installAddr": "幸福里"}
    for invalid in ({"elderId": "E001"}, {"deviceNo": "EDGE-001"}):
        response_data(
            await client.post("devices", headers=manager, json={**body, **invalid}), code=1005
        )
    response_data(
        await client.post("devices", headers=manager, json={**body, "elderId": "E005"}), code=1004
    )
    created = response_data(await client.post("devices", headers=manager, json=body), status=201)
    assert created["elder"]["id"] == "E004" and created["status"] == 0
    for invalid in ({"elderId": "E002"}, {"deviceNo": "ANOTHER"}, {"config": {"roi": [[1.1, 0]]}}):
        response_data(await client.put("devices/D001", headers=manager, json=invalid), code=1001)
    patch = {"config": {"furniture": [{"type": "bed", "points": [[0.5, 0.7]]}]}}
    updated = response_data(await client.put("devices/D001", headers=manager, json=patch))
    assert updated == response_data(await client.get("devices/D001", headers=manager))
    assert updated["config"] == {
        "roi": [[0.2, 0.3]],
        "quietHours": ["22:00-06:00"],
        **patch["config"],
    }
    async with factory() as db:
        audits = list(await db.scalars(select(AuditLog).order_by(AuditLog.created_at)))
        assert [(row.action, row.target) for row in audits] == [
            ("CREATE_DEVICE", created["id"]),
            ("UPDATE_DEVICE", "D001"),
        ]


async def test_concurrent_device_creation_for_one_elder(records_app):
    client, headers, factory = records_app
    payloads = [{"deviceNo": no, "elderId": "E004", "type": 1} for no in ("RACE-1", "RACE-2")]
    responses = await asyncio.gather(
        *(client.post("devices", headers=headers["admin"], json=p) for p in payloads)
    )
    assert {(response.status_code, response.json()["code"]) for response in responses} == {
        (201, 0),
        (200, 1005),
    }
    async with factory() as db:
        assert (
            await db.scalar(
                select(func.count()).select_from(Device).where(Device.elder_id == "E004")
            )
            == 1
        )
