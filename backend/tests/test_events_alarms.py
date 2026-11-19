import asyncio
import os
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from redis.asyncio import Redis
from sqlalchemy import func, select
from test_records import records_server as records_server  # noqa: PLC0414 - shared pytest fixture
from test_records import response_data

from app.core.config import Settings
from app.core.exceptions import BizException
from app.main import create_app
from app.models import Alarm, AlarmAction, AuditLog, Device, Elder, Event, FamilyBinding, User
from app.services import alarm_service, event_service
from app.services.notify import dispatcher


@pytest.fixture
async def m5(records_server):
    app, client, headers, factory = records_server
    elder_id = uuid4().hex
    device_no = "EDGE-" + elder_id
    async with factory.begin() as db:
        db.add(
            User(
                id="SYSTEM",
                username="SYSTEM",
                password_hash="unused",
                nickname="系统",
                role_code="VIEWER",
                status=0,
            )
        )
        db.add(
            Elder(
                id=elder_id,
                name="王秀兰",
                gender=2,
                birth_date=date(1948, 3, 2),
                address="幸福里",
                room_no="301",
                guardian_id="G001",
                community_id="C001",
                phone="13812345678",
                health_tags=["独居"],
                emergency_contact=[{"primary": True, "name": "张女士", "relation": "子女"}],
            )
        )
        await db.flush()
        db.add(Device(id=elder_id, device_no=device_no, elder_id=elder_id, type=1))
        db.add(
            FamilyBinding(
                id=elder_id, elder_id=elder_id, user_id="family01", relation="子女", is_primary=True
            )
        )
        (await db.get(User, "family01")).nickname = "张女士"
    if not os.getenv("TEST_REDIS_URL"):
        # The full acceptance run uses Redis 7. This substitute covers NX semantics on PG-only CI.
        keys = {}

        async def reserve(key, value, *, nx=False, ex, get=False):
            previous = keys.get(key)
            if not nx or previous is None:
                keys[key] = value
            return previous if get else True

        app.state.redis.set.side_effect = reserve
    return SimpleNamespace(
        app=app,
        client=client,
        headers=headers,
        factory=factory,
        elder=elder_id,
        device=device_no,
        body={
            "elderId": elder_id,
            "type": "FALL",
            "level": "P0",
            "confidence": 0.93,
            "eventId": "m5-first",
        },
    )


async def request(m, method, path, who="admin", code=0, **kwargs):
    response = await m.client.request(method, path, headers=m.headers[who], **kwargs)
    return response_data(response, code=code)


async def mock_event(m, **changes):
    return await request(m, "POST", "events/mock", json={**m.body, **changes})


def test_production_routes():
    for env, count in [("prod", 12), ("development", 13)]:
        app = create_app(Settings(_env_file=None, app_env=env))
        paths = app.openapi()["paths"]
        paths = {
            p: ops for p, ops in paths.items() if p.startswith(("/api/v1/events", "/api/v1/alarms"))
        }
        assert sum(len(ops) for ops in paths.values()) == count
        assert ("/api/v1/events/mock" in paths) == (env != "prod")


def test_transition_matrix():
    valid = {
        "PENDING": {"ACKNOWLEDGED", "ESCALATED"},
        "ACKNOWLEDGED": {"RESOLVED", "FALSE_POSITIVE"},
        "ESCALATED": {"ACKNOWLEDGED", "COMMUNITY_DISPATCHED"},
        "COMMUNITY_DISPATCHED": {"RESOLVED", "FALSE_POSITIVE"},
        "RESOLVED": set(),
        "FALSE_POSITIVE": set(),
    }
    for source, allowed in valid.items():
        for target in valid:
            alarm = Alarm(id="test", status=source)
            db = Mock()
            at = datetime.now(UTC)
            if target in allowed:
                entry = alarm_service.transition(db, alarm, target, "SYSTEM", {}, at)
                assert entry.action == alarm_service.TRANSITION_ACTION[target]
                db.add.assert_called_once_with(entry)
                assert alarm.status == target
            else:
                with pytest.raises(BizException, match="当前状态不允许该操作") as exc:
                    alarm_service.transition(db, alarm, target, "SYSTEM", {}, at)
                db.add.assert_not_called()
                assert exc.value.code == 1005 and alarm.status == source


async def test_replay_dedup_ack_false_positive_and_timeline(m5):
    m = m5
    first, replay = await asyncio.gather(mock_event(m), mock_event(m))
    alarm, event = first["alarm"], first["event"]
    assert replay["event"]["id"] == event["id"] and replay["alarm"]["id"] == alarm["id"]
    path = "alarms/" + alarm["id"]
    assert alarm["status"] == "PENDING" and 0 < alarm["remainingSec"] <= 60

    duplicates = await asyncio.gather(*(mock_event(m, eventId=f"repeat-{i}") for i in range(3)))
    assert all(item["alarm"] is None for item in duplicates)
    repeated = await mock_event(m, eventId="repeat-0")
    assert repeated["event"]["id"] == duplicates[0]["event"]["id"] and repeated["alarm"] is None
    if os.getenv("TEST_REDIS_URL"):
        assert 0 < await m.app.state.redis.ttl(f"alarm:dedup:{m.elder}:FALL") <= 300

    denied = await request(
        m, "POST", path + "/resolve", code=1005, json={"result": "TRUE_FALL", "needFollowUp": False}
    )
    assert denied is None
    acknowledgments = await asyncio.gather(
        *(
            m.client.post(path + "/ack", headers=m.headers["family01"], json={"note": "收到"})
            for _ in range(2)
        )
    )
    assert sorted(r.json()["code"] for r in acknowledgments) == [0, 1005]
    ack = next(r.json()["data"] for r in acknowledgments if r.json()["code"] == 0)
    assert ack["ackAt"] and ack["status"] == "ACKNOWLEDGED" and ack["remainingSec"] is None
    resolution = {"result": "FALSE_POSITIVE", "note": "家属核实", "needFollowUp": True}
    resolved = await request(m, "POST", path + "/resolve", json=resolution)
    assert resolved["status"] == "FALSE_POSITIVE" and resolved["resolvedAt"]
    expected = datetime.fromisoformat(ack["ackAt"]) - datetime.fromisoformat(alarm["notifiedAt"])
    assert resolved["responseSec"] == int(expected.total_seconds())
    await request(m, "POST", path + "/ack", code=1005, json={})
    await request(m, "POST", path + "/resolve", code=1005, json=resolution)
    detail = await request(m, "GET", path)
    actions = detail["actions"]
    assert [a["action"] for a in actions] == [
        "NOTIFY",
        "NOTIFY",
        "DEDUP",
        "DEDUP",
        "DEDUP",
        "ACK",
        "MARK_FALSE",
    ]
    assert {a["channel"] for a in actions[:2]} == {"PUSH", "SMS"}
    assert all(a["result"] == "SENT" for a in actions[:2])
    assert all(a["actor"] == "SYSTEM" for a in actions[:5])
    assert actions[-1]["detail"] == resolution
    assert (
        detail["elder"]["phone"] == "138****5678"
        and detail["elder"]["primaryContact"]["name"] == "张女士"
    )
    assert detail["event"]["handleResult"] == "FALSE_POSITIVE" and detail["event"]["handled"]
    assert detail["event"]["handleRemark"] == "家属核实" and detail["event"]["handledAt"]
    timeline = detail["timeline"]
    assert [item["ts"] for item in timeline] == sorted(item["ts"] for item in timeline)
    assert all(item["ts"].endswith("+08:00") for item in timeline)
    assert [t["text"] for t in timeline][:2] == ["检测到跌倒（置信度 93%）", "已推送家属（张女士）"]
    assert timeline[-2]["text"] == "家属张女士已确认" and timeline[-1]["text"].endswith("误报")
    assert (await mock_event(m, eventId="closed-in-window"))["alarm"] is None
    async with m.factory() as db:
        assert (
            await db.scalar(
                select(func.count()).select_from(Event).where(Event.event_id == m.body["eventId"])
            )
            == 1
        )
        assert (
            await db.scalar(
                select(func.count()).select_from(Alarm).where(Alarm.elder_id == m.elder)
            )
            == 1
        )
        assert (
            await db.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(AuditLog.action == "INGEST_EVENT", AuditLog.target == event["id"])
            )
            == 1
        )


async def test_scope_filters_media_and_event_handling(m5):
    m = m5
    report = await mock_event(m)
    other = await mock_event(m, elderId="E002", eventId="m5-other")
    event, alarm = other["event"], other["alarm"]
    for who in ("family01", "guardian01"):
        await request(m, "POST", "alarms/" + alarm["id"] + "/ack", who, 1003, json={})
    await request(
        m,
        "POST",
        "alarms/" + alarm["id"] + "/dispatch",
        "guardian01",
        1003,
        json={"guardianId": "G002"},
    )
    await request(
        m,
        "POST",
        "alarms/" + report["alarm"]["id"] + "/resolve",
        "guardian01",
        1003,
        json={"result": "TRUE_FALL", "needFollowUp": False},
    )
    await request(
        m, "POST", "events/mock", "community01", 1003, json=m.body | {"eventId": "m5-other"}
    )
    for path in (
        "events/" + event["id"],
        "events/" + event["id"] + "/media",
        "alarms/" + alarm["id"],
    ):
        await request(m, "GET", path, "guardian01", 1004)
    for path in ("events", "alarms"):
        data = await request(m, "GET", path, "guardian01", params={"elderId": "E002"})
        assert data["total"] == 0 and data["list"] == []
        assert (await request(m, "GET", path + "/stats", "guardian02", params={"range": "today"}))[
            "total"
        ] == 1
    assert (await request(m, "GET", "alarms/pending-count", "guardian02")) == {"count": 1}
    assert (
        await request(
            m,
            "GET",
            "alarms",
            "guardian02",
            params={
                "elderId": "E002",
                "status": "PENDING",
                "level": "P0",
                "startTime": alarm["createdAt"],
                "endTime": alarm["createdAt"],
            },
        )
    )["total"] == 1

    payload = {
        "deviceNo": m.device,
        "eventId": "edge-p2",
        "type": "LONG_LIE",
        "level": "P2",
        "confidence": 0.81,
        "features": {"trackId": 3, "extra": [1, 2]},
        "algoVersion": "v5",
        "snapshotUrl": "minio://events/s.jpg",
        "clipUrl": "minio://events/c.mp4",
    }
    async with m.factory() as db:
        record, no_alarm = await event_service.ingest(db, payload)
        assert no_alarm is None
        event_path = "events/" + record.id
    media = await request(m, "GET", event_path + "/media")
    assert media["snapshotUrl"] == payload["snapshotUrl"] and media["clipUrl"] == payload["clipUrl"]
    detail = await request(m, "GET", event_path)
    assert detail["features"] == payload["features"] and detail["algoVersion"] == "v5"
    await request(
        m, "PUT", event_path + "/handle", "guardian01", 1003, json={"result": "TRUE_FALL"}
    )
    data = await request(
        m, "PUT", event_path + "/handle", json={"result": "TRUE_FALL", "remark": "已上门确认"}
    )
    filters = {
        "elderId": m.elder,
        "deviceId": record.device_id,
        "type": "LONG_LIE",
        "level": "P2",
        "handled": "true",
        "startTime": data["occurredAt"],
        "endTime": data["occurredAt"],
        "pageSize": 1,
    }
    result = await request(m, "GET", "events", "guardian01", params=filters)
    assert result["total"] == 1 and result["pageSize"] == 1
    item = result["list"][0]
    assert item["handleRemark"] == "已上门确认" and item["handledAt"] == data["handledAt"]
    assert item["handleResult"] == "TRUE_FALL" and item["handled"]
    assert (await request(m, "GET", "events", "guardian01", params={**filters, "page": 2}))[
        "list"
    ] == []
    assert (
        await request(m, "GET", "events", "guardian01", params={**filters, "handled": "false"})
    )["total"] == 0
    await request(m, "GET", "events", code=1001, params={"range": "bad", "startTime": "not-time"})
    for span in ("today", "7d", "30d"):
        stats = await request(m, "GET", "events/stats", "guardian01", params={"range": span})
        assert stats["todayTotal"] == 2 and stats["todayP0"] == 1 and stats["byLevel"]["p2"] == 1


async def test_dispatch_and_resolution_without_ack(m5):
    m = m5
    first = await mock_event(m, level="P1")
    alarm_id = first["alarm"]["id"]
    path = "alarms/" + alarm_id
    await request(m, "POST", path + "/dispatch", code=1005, json={"guardianId": "G01"})
    async with m.factory.begin() as db:
        alarm = await db.get(Alarm, alarm_id)
        alarm.notified_at = datetime.now(UTC) - timedelta(days=1, seconds=67)
        alarm_service.transition(
            db, alarm, "ESCALATED", "SYSTEM", {"to": "guardian01"}, datetime.now(UTC)
        )
    await request(m, "POST", path + "/dispatch", "guardian01", 1004, json={"guardianId": "G02"})
    data = await request(
        m, "POST", path + "/dispatch", "guardian01", json={"guardianId": "G01", "note": "上门"}
    )
    assert data["status"] == "COMMUNITY_DISPATCHED" and data["currentHandler"] == "guardian01"
    data = await request(
        m, "POST", path + "/resolve", json={"result": "TRUE_FALL", "needFollowUp": False}
    )
    assert data["status"] == "RESOLVED" and data["responseSec"] >= 86467
    await request(m, "POST", path + "/ack", "family01", 1005, json={})
    detail = await request(m, "GET", path)
    assert [a["action"] for a in detail["actions"]] == ["NOTIFY", "ESCALATE", "DISPATCH", "RESOLVE"]
    assert detail["timeline"][-1]["text"] == "已完结，结果：真实跌倒"


async def test_ingest_validation_failure_and_post_commit_notification_failure(m5, monkeypatch):
    m = m5
    payload = {**m.body, "deviceNo": m.device}
    async with m.factory() as db:
        with pytest.raises(BizException, match="设备不存在") as error:
            await event_service.ingest(
                db, payload | {"deviceNo": "missing"}, redis=m.app.state.redis
            )
        assert error.value.code == 1004
        assert not await db.scalar(select(Event.id).where(Event.elder_id == m.elder))
        assert not await db.scalar(select(Alarm.id).where(Alarm.elder_id == m.elder))
        assert not await db.scalar(select(AlarmAction.id))
        with monkeypatch.context() as patch:
            patch.setattr(
                dispatcher,
                "notify_new_alarm",
                AsyncMock(side_effect=RuntimeError("inject failure")),
            )
            event, alarm = await event_service.ingest(
                db, payload, redis=m.app.state.redis, escalation=m.app.state.escalation
            )
        assert alarm.status == "PENDING"
        assert await db.scalar(select(Event.id).where(Event.id == event.id)) == event.id
        assert await db.scalar(select(Alarm.id).where(Alarm.id == alarm.id)) == alarm.id
        assert not await db.scalar(select(AlarmAction.id))
        _, replayed = await event_service.ingest(db, payload, redis=m.app.state.redis)
        assert replayed.id == alarm.id


async def test_redis_failure_degrades(m5, monkeypatch, capsys, unused_tcp_port):
    m = m5
    async with Redis(host="127.0.0.1", port=unused_tcp_port) as offline:
        monkeypatch.setattr(m.app.state, "redis", offline)
        first = await mock_event(m)
        second = await mock_event(m, eventId="offline-2")
        assert first["alarm"]["id"] != second["alarm"]["id"]
        assert (await mock_event(m))["alarm"]["id"] == first["alarm"]["id"]
    assert "alarm_redis_degraded" in capsys.readouterr().out
