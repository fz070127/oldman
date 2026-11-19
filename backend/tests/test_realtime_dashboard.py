import asyncio
import json
from contextlib import AsyncExitStack
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock

import pytest
import uvicorn
from sqlalchemy import delete, update
from test_events_alarms import m5 as m5  # noqa: PLC0414
from test_events_alarms import mock_event, request
from test_records import records_server as records_server  # noqa: PLC0414
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

from app.core.tokens import TokenIssuer
from app.models import Alarm, Device, Event
from app.models.enums import RoleCode
from app.mqtt.handlers import MqttHandlers
from app.schemas.records import CHINA
from app.services.device_presence import DevicePresence
from app.services.notify.ws import WsNotifier
from app.ws.manager import ConnectionManager


async def test_failed_socket_is_removed_without_stopping_other_deliveries():
    manager = ConnectionManager()
    user = Mock(id="user", community_id="community", role_code=RoleCode.COMMUNITY_ADMIN)
    failed = AsyncMock()
    healthy = AsyncMock()
    failed.send_json.side_effect = OSError
    for ws in (failed, healthy):
        await manager.connect(ws, user)
    message = {"type": "ALARM_UPDATE", "data": {"alarmId": "alarm"}}
    assert await manager.broadcast_to_community("community", message) == 1
    assert manager.by_user == {"user": {healthy}}
    assert manager.by_community == {"community": {healthy}}
    assert set(manager.all) == {healthy}
    healthy.send_json.assert_awaited_once_with(message)
    assert (await WsNotifier(manager).send("user", "", "", {"ws_message": message})).success
    assert await manager.broadcast_all(message) == 1
    manager.disconnect(healthy)
    assert not any((manager.all, manager.by_community, manager.by_user))


@pytest.fixture
async def ws_url(m5):
    config = uvicorn.Config(m5.app, host="127.0.0.1", port=0, lifespan="off", log_level="critical")
    server = uvicorn.Server(config)
    serving = asyncio.create_task(server.serve())
    try:
        async with asyncio.timeout(5):
            while not server.started:
                await asyncio.sleep(0.01)
        port = server.servers[0].sockets[0].getsockname()[1]
        yield f"ws://127.0.0.1:{port}/api/v1/ws"
    finally:
        server.should_exit = True
        await asyncio.wait_for(serving, 5)


def ws_client(m5, url, who):
    token = m5.headers[who]["Authorization"].removeprefix("Bearer ")
    return connect(f"{url}?token={token}")


async def read_message(ws):
    return json.loads(await asyncio.wait_for(ws.recv(), 3))


async def ping(ws):
    await ws.send('{"type":"PING"}')
    assert await read_message(ws) == {"type": "PONG"}


async def test_ws_rejects_bad_access_tokens_and_closes_idle_sockets(m5, ws_url, monkeypatch):
    monkeypatch.setattr("app.api.v1.ws.IDLE_SECONDS", 0.05)
    refresh = TokenIssuer(m5.app.state.settings).issue("admin")["refreshToken"]
    for query in ("", "?token=invalid", f"?token={refresh}"):
        async with connect(ws_url + query) as ws:
            with pytest.raises(ConnectionClosed):
                await asyncio.wait_for(ws.recv(), 3)
        assert ws.close_code == 4401
    async with ws_client(m5, ws_url, "admin") as ws:
        with pytest.raises(ConnectionClosed):
            await asyncio.wait_for(ws.recv(), 3)
    assert ws.close_code == 4408


async def test_alarm_push_scope_and_committed_updates(m5, ws_url):
    async with AsyncExitStack() as stack:
        sockets = {
            who: await stack.enter_async_context(ws_client(m5, ws_url, who))
            for who in ("admin", "family01", "guardian01", "guardian02", "community01", "viewer01")
        }
        await ping(sockets["admin"])
        count_before = await request(m5, "GET", "alarms/pending-count", "viewer01")
        family_before = await request(m5, "GET", "alarms/pending-count", "family01")
        alarm = (await mock_event(m5))["alarm"]
        targets = [ws for who, ws in sockets.items() if who != "guardian02"]
        signals = [await read_message(ws) for ws in targets]
        assert all(signal == signals[0] for signal in signals)
        assert set(signals[0]) == {"type", "ts", "data"}
        assert signals[0]["type"] == "ALARM_NEW"
        assert signals[0]["data"] | {"remainingSec": 60} == {
            "alarmId": alarm["id"],
            "level": "P0",
            "elderId": m5.elder,
            "elderName": "王秀兰",
            "communityName": "幸福里",
            "roomNo": "301",
            "eventType": "FALL",
            "confidence": 0.93,
            "occurredAt": signals[0]["data"]["occurredAt"],
            "snapshotUrl": None,
            "remainingSec": 60,
        }
        assert 0 < signals[0]["data"]["remainingSec"] <= 60
        await ping(sockets["guardian02"])
        for who, before in (("viewer01", count_before), ("family01", family_before)):
            assert await request(m5, "GET", "alarms/pending-count", who) == {
                "count": before["count"] + 1
            }

        path = f"alarms/{alarm['id']}"
        for action, body in (
            ("ack", {}),
            ("resolve", {"result": "TRUE_FALL", "needFollowUp": False}),
        ):
            changed = await request(m5, "POST", f"{path}/{action}", json=body)
            for ws in targets:
                signal = await read_message(ws)
                assert signal["type"] == "ALARM_UPDATE"
                assert signal["data"] == {
                    "alarmId": alarm["id"],
                    "status": changed["status"],
                    "escalateStep": changed["escalateStep"],
                    "currentHandler": changed["currentHandler"],
                }
        await ping(sockets["guardian02"])


async def test_escalation_broadcasts_once_to_ws_channel_recipient(m5, ws_url, monkeypatch):
    engine = m5.app.state.escalation
    async with (
        ws_client(m5, ws_url, "admin") as admin,
        ws_client(m5, ws_url, "community01") as community,
    ):
        alarm = (await mock_event(m5))["alarm"]
        for ws in (admin, community):
            assert (await read_message(ws))["type"] == "ALARM_NEW"
        monkeypatch.setattr(engine, "schedule", AsyncMock())
        async with m5.factory.begin() as db:
            stored = await db.get(Alarm, alarm["id"])
            stored.notified_at = datetime.now(UTC) - timedelta(seconds=125)
        for step in (1, 2):
            assert await engine.process(alarm["id"], step)
            for ws in (admin, community):
                signal = await read_message(ws)
                assert signal["type"] == "ALARM_UPDATE"
                assert signal["data"]["status"] == "ESCALATED"
                assert signal["data"]["escalateStep"] == step
        await ping(community)


async def test_heartbeat_and_expiry_publish_only_transitions(m5, ws_url):
    state = m5.app.state
    realtime = state.db_sessionmaker.kw["info"]["realtime"]
    handlers = MqttHandlers(m5.factory, state.redis, state.mqtt_publisher, realtime)
    presence = DevicePresence(m5.factory, realtime)
    heartbeat = json.dumps({"ts": datetime.now(UTC).isoformat(), "fps": 15, "cpu": 20, "mem": 10})
    async with ws_client(m5, ws_url, "admin") as ws:
        await handlers.on_heartbeat(m5.device, heartbeat.encode())
        online = await read_message(ws)
        assert online["type"] == "DEVICE_STATUS"
        assert online["data"]["status"] == 1
        assert online["ts"].endswith("+08:00")
        assert online["data"]["lastHeartbeat"].endswith("+08:00")
        await handlers.on_heartbeat(m5.device, heartbeat.encode())
        await presence.scan()
        await ping(ws)
        async with m5.factory.begin() as db:
            await db.execute(
                update(Device)
                .where(Device.device_no == m5.device)
                .values(last_heartbeat=datetime.now(UTC) - timedelta(seconds=91))
            )
        await presence.scan()
        offline = await read_message(ws)
        assert offline["data"]["status"] == 2
        assert set(offline["data"]) == {"deviceId", "deviceNo", "status", "lastHeartbeat"}
        async with m5.factory() as db:
            assert (await db.get(Device, m5.elder)).status == 2
        await presence.scan()
        await ping(ws)


async def test_dashboard_sql_metrics_zero_days_and_scope(m5):
    now = datetime.now(CHINA)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    first = (await mock_event(m5))["alarm"]
    older = (await mock_event(m5, elderId="E002", eventId="m7-older", level="P1"))["alarm"]
    async with m5.factory.begin() as db:
        first_alarm = await db.get(Alarm, first["id"])
        first_alarm.ack_at = first_alarm.notified_at + timedelta(seconds=47)
        older_alarm = await db.get(Alarm, older["id"])
        older_alarm.created_at = today - timedelta(seconds=1, days=1)
        older_alarm.notified_at = older_alarm.created_at
        older_alarm.ack_at = older_alarm.notified_at + timedelta(seconds=200)
        first_event = await db.get(Event, first_alarm.event_id)
        first_event.handled = True
        first_event.handle_result = "FALSE_POSITIVE"
        (await db.get(Device, "D001")).last_heartbeat = now - timedelta(seconds=15)
        (await db.get(Device, "D002")).last_heartbeat = now - timedelta(seconds=91)
        db.add_all(
            Event(
                id=f"m7-ev-{index}",
                event_id=f"m7-ev-{index}",
                device_id="D001",
                elder_id="E001",
                type="FALL",
                level="P2",
                confidence=0.7,
                occurred_at=now - timedelta(minutes=index + 1),
            )
            for index in range(21)
        )

    overview = await request(m5, "GET", "dashboard/overview")
    assert set(overview) == {
        "elderTotal",
        "elderOnline",
        "deviceTotal",
        "deviceOnline",
        "deviceOffline",
        "alarmToday",
        "alarmPending",
        "alarmP0Today",
        "avgResponseSec",
        "falsePositiveRate",
        "updatedAt",
    }
    assert overview["avgResponseSec"] == 47 and overview["falsePositiveRate"] == 1
    assert overview["alarmToday"] == overview["alarmP0Today"] == 1
    assert overview["elderOnline"] == overview["deviceOnline"] == 1
    assert overview["updatedAt"].endswith("+08:00")
    trend = (await request(m5, "GET", "dashboard/trend?days=7"))["list"]
    assert len(trend) == 7
    for index, row in enumerate(trend):
        assert row == {
            "date": (today.date() - timedelta(days=6 - index)).isoformat(),
            "p0": int(index == 6),
            "p1": int(index in {3, 4}),
            "p2": 0,
            "total": int(index in {3, 4, 6}),
        }
    distribution = (await request(m5, "GET", "dashboard/distribution", "viewer01"))["list"]
    assert len(distribution) == 1
    community = distribution[0]
    assert community["communityId"] == "C001" and community["alarmToday"] == 1
    assert 0 <= community["x"] <= 1 and 0 <= community["y"] <= 1
    events = (await request(m5, "GET", "dashboard/realtime", "viewer01"))["list"]
    assert len(events) == 20 and events[0]["id"] == first_alarm.event_id
    assert all(event["communityId"] == "C001" for event in events)
    assert all(event["occurredAt"].endswith("+08:00") for event in events)
    summary = await request(m5, "GET", "dashboard/device-status")
    assert summary["online"] == 1
    assert len(summary["offlineList"]) == summary["total"] - summary["online"]
    assert {item["id"] for item in summary["offlineList"]}.isdisjoint({"D001"})
    await request(m5, "GET", "dashboard/overview", "family01", code=1003)


@pytest.mark.parametrize(("days", "code"), [(1, 0), (90, 0), (91, 1001)])
async def test_trend_boundaries_on_empty_scope(m5, days, code):
    async with m5.factory.begin() as db:
        await db.execute(delete(Alarm))
    data = await request(m5, "GET", f"dashboard/trend?days={days}", code=code)
    if code == 0:
        assert len(data["list"]) == days
        assert all(
            item["total"] == item["p0"] == item["p1"] == item["p2"] == 0 for item in data["list"]
        )
    else:
        assert data is None
