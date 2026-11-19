import asyncio
import json
import os
from datetime import datetime
from unittest.mock import AsyncMock

import pytest
from redis.asyncio import Redis
from sqlalchemy import select
from test_events_alarms import m5 as m5  # noqa: PLC0414 - shared pytest fixture
from test_events_alarms import mock_event, request
from test_records import records_server as records_server  # noqa: PLC0414 - shared pytest fixture

from app.core.config import Settings
from app.models import Alarm, Notification, User
from app.services.escalation_rules import EscalationRules
from app.services.escalation_service import QUEUE_KEY, EscalationEngine, EscalationQueue
from app.services.notify import dispatcher
from app.services.notify.base import NotifyResult


async def wait_for_alarm(m, path, predicate):
    async with asyncio.timeout(20):
        while True:
            alarm = await request(m, "GET", path)
            if predicate(alarm):
                return alarm
            await asyncio.sleep(0.05)


def test_rules_reload_and_validation(tmp_path):
    path = tmp_path / "escalate.yaml"
    path.write_text(
        "default: [{after_sec: 60, to: family_primary, channels: [PUSH]}]\nlevels: {P0: default}\n",
        encoding="utf-8",
    )
    rules = EscalationRules(Settings(_env_file=None, escalate_config_path=path))
    assert rules.window("P0", 1) == 60
    path.write_text(path.read_text().replace("60", "5"), encoding="utf-8")
    rules.reload()
    assert rules.window("P0", 1) == 5
    path.write_text(path.read_text().replace("5", "-5"), encoding="utf-8")
    with pytest.raises(ValueError):
        rules.reload()
    assert rules.window("P0", 1) == 5


async def test_offline_queue_escalates_and_skips_ack(m5, unused_tcp_port, capsys, monkeypatch):
    engine = m5.app.state.escalation
    engine.rules.time_scale = 1 / 120
    engine.interval = 0.1
    monkeypatch.setattr(dispatcher, "RETRY_DELAYS", (0, 0))
    async with Redis(host="127.0.0.1", port=unused_tcp_port) as offline:
        monkeypatch.setattr(engine, "queue", EscalationQueue(offline))
        first = (await mock_event(m5))["alarm"]
        second = (await mock_event(m5, elderId="E002", eventId="m6-ack"))["alarm"]
        path = "alarms/" + first["id"]
        ack_path = "alarms/" + second["id"]
        assert (await request(m5, "POST", ack_path + "/ack", json={}))["status"] == "ACKNOWLEDGED"
        alarm = await wait_for_alarm(
            m5,
            path,
            lambda a: (
                sum(x["action"] == "ESCALATE" for x in a["actions"]) == 3
                and len([x for x in a["actions"] if x["action"] == "NOTIFY"]) == 8
            ),
        )
        assert alarm["status"] == "ESCALATED" and alarm["escalateStep"] == 3
        assert alarm["remainingSec"] is None
        assert [
            (action["detail"]["step"], action["detail"]["to"])
            for action in alarm["actions"]
            if action["action"] == "ESCALATE"
        ] == [(1, "guardian01"), (2, "community01"), (3, "community01")]
        acknowledged = await request(m5, "GET", ack_path)
        assert acknowledged["escalateStep"] == 0
        failed = [a for a in acknowledged["actions"] if a["action"] == "NOTIFY"]
        assert len(failed) == 2
        assert all(
            a["result"] == "FAILED" and a["detail"]["reason"] == "recipient_missing" for a in failed
        )
        assert all(
            action["detail"]["attempts"] == 3 and action["result"] == "FAILED"
            for action in alarm["actions"]
            if action["channel"] == "WS"
        )
    logs = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert any(
        entry["event"] == "alarm_escalation_redis_degraded"
        and "lost on restart" in entry["message"]
        for entry in logs
    )
    assert any(
        entry["event"] == "alarm_escalation_skipped"
        and entry["alarm_id"] == second["id"]
        and entry["status"] == "ACKNOWLEDGED"
        for entry in logs
    )


async def test_redis_restart_and_concurrent_workers(m5, monkeypatch):
    if not os.getenv("TEST_REDIS_URL"):
        pytest.skip("Set TEST_REDIS_URL to verify persistent escalation jobs")

    env = Settings(_env_file=None, escalate_time_scale=1 / 12, escalate_poll_interval_sec=0.1)
    initial = m5.app.state.escalation
    initial.rules.time_scale = env.escalate_time_scale
    initial.interval = 60
    monkeypatch.setattr(dispatcher, "RETRY_DELAYS", (0, 0))
    redis = m5.app.state.redis
    alarm = (await mock_event(m5))["alarm"]
    alarm_id = alarm["id"]
    path = "alarms/" + alarm_id
    try:
        remaining = (await request(m5, "GET", path))["remainingSec"]
        assert 0 < remaining <= 5
        assert await redis.zscore(QUEUE_KEY, f"{alarm_id}:1") == (
            datetime.fromisoformat(alarm["notifiedAt"]).timestamp() + 5
        )
        # The replacement scanners start empty and share only PostgreSQL and the Redis ZSET.
        async with (
            Redis.from_url(os.environ["TEST_REDIS_URL"]) as first,
            Redis.from_url(os.environ["TEST_REDIS_URL"]) as second,
        ):
            engines = [EscalationEngine(env, m5.factory, client) for client in (first, second)]
            workers = [asyncio.create_task(engine.run()) for engine in engines]
            try:
                await wait_for_alarm(m5, path, lambda a: a["escalateStep"] == 3)
                await asyncio.gather(*(engine.process(alarm_id, 3) for engine in engines))
                result = await request(m5, "GET", path)
                applied = [a for a in result["actions"] if a["action"] == "ESCALATE"]
                start = datetime.fromisoformat(alarm["notifiedAt"])
                actual = [
                    (datetime.fromisoformat(a["createdAt"]) - start).total_seconds()
                    for a in applied
                ]
                assert len(applied) == 3
                for elapsed, expected in zip(actual, (5, 10, 15), strict=True):
                    assert expected <= elapsed < expected + 2
            finally:
                for worker in workers:
                    worker.cancel()
                await asyncio.gather(*workers, return_exceptions=True)
    finally:
        await redis.zrem(QUEUE_KEY, *(f"{alarm_id}:{step}" for step in range(1, 4)))


async def test_dispatcher_retries_independently_and_writes_inbox(m5, monkeypatch):
    monkeypatch.setattr(dispatcher, "RETRY_DELAYS", (0, 0))
    engine = m5.app.state.escalation
    push = engine.notifiers["PUSH"]
    inbox = engine.notifiers["INBOX"]
    inbox_written = asyncio.Event()
    real_inbox = inbox.send

    async def send_inbox(*args):
        result = await real_inbox(*args)
        inbox_written.set()
        return result

    async def send_push(*_):
        async with asyncio.timeout(2):
            await inbox_written.wait()
        return NotifyResult(False, "PUSH", {"reason": "test_failure"})

    alarm_id = (await mock_event(m5))["alarm"]["id"]
    monkeypatch.setattr(push, "send", AsyncMock(side_effect=send_push))
    monkeypatch.setattr(inbox, "send", send_inbox)
    async with m5.factory() as db:
        alarm = await db.get(Alarm, alarm_id)
        recipient = await db.get(User, "admin")
    rule = engine.rules.target("P0", 0).model_copy(
        update={"to": "admin", "channels": ("PUSH", "INBOX")}
    )
    await dispatcher.notify_alarm(alarm, 1, rule, recipient, m5.factory, engine.notifiers)
    assert push.send.await_count == 3
    async with m5.factory() as db:
        notification = await db.scalar(select(Notification).where(Notification.biz_id == alarm_id))
        assert notification.user_id == "admin" and notification.type == "ALARM"
    result = await request(m5, "GET", "alarms/" + alarm_id)
    attempts = {a["channel"]: a for a in result["actions"] if a["detail"]["step"] == 1}
    assert attempts["INBOX"]["result"] == "SENT"
    assert attempts["PUSH"]["result"] == "FAILED" and attempts["PUSH"]["detail"]["attempts"] == 3
