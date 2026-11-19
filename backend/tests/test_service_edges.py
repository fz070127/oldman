import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from app.models import Guardian
from app.services import device_presence
from app.services.notify.base import NotifyResult
from app.services.notify.registry import build_registry
from app.services.records import mask_audit_phones, resolve_directory_id


@pytest.mark.parametrize(
    ("provided", "exact", "expected"),
    [("G01", "G01", "G01"), ("G01", None, "G001"), ("G001", None, "G001")],
)
async def test_resolve_demo_guardian_id_preserves_stored_ids(provided, exact, expected):
    db = Mock(scalar=AsyncMock(return_value=exact))
    assert await resolve_directory_id(db, Guardian, provided) == expected
    assert db.scalar.await_count == int(len(provided) == 3)


def test_mask_audit_phones_in_nested_payload():
    detail = {
        "Phone": "1234567",
        "contact": [{"phone": 13900001234}, {"phone": None, "relation": "子女"}],
    }
    assert mask_audit_phones(detail) == {
        "Phone": "*******",
        "contact": [{"phone": "139****1234"}, {"phone": None, "relation": "子女"}],
    }


async def test_presence_worker_recovers_after_scan_failure(monkeypatch):
    worker = device_presence.DevicePresence(None, None)
    worker.scan = AsyncMock(side_effect=[OSError("database unavailable"), None])
    delay = AsyncMock(side_effect=[None, asyncio.CancelledError()])
    logger = Mock()
    monkeypatch.setattr(device_presence, "asyncio", SimpleNamespace(sleep=delay))
    monkeypatch.setattr(device_presence, "log", logger)

    with pytest.raises(asyncio.CancelledError):
        await worker.run()

    assert worker.scan.await_count == 2
    logger.exception.assert_called_once_with("device_offline_scan_failed")
    assert delay.await_count == 2


@pytest.mark.parametrize("channel", ["PUSH", "SMS", "CALL"])
@pytest.mark.parametrize("provider", ["mock", "aliyun"])
async def test_external_notification_delivery_configuration(provider, channel, monkeypatch):
    from app.services.notify import mock

    logger = Mock()
    monkeypatch.setattr(mock, "log", logger)
    registry = build_registry(provider, None, None)
    assert registry.keys() == {"PUSH", "SMS", "CALL", "INBOX", "WS"}
    ctx = {"alarm_id": "a1", "user_id": "family01", "step": 0}
    result = await registry[channel].send("family01", "告警", "请确认", ctx)
    assert result == NotifyResult(True, channel, {"provider": "mock"})
    logger.info.assert_called_once_with("alarm_notify_mock", channel=channel, **ctx)
    assert logger.warning.call_count == int(provider == "aliyun")


@pytest.mark.parametrize("has_message", [True, False])
async def test_ws_notification_when_recipient_is_offline(has_message):
    connections = Mock(broadcast_to_user=AsyncMock(return_value=0))
    notifier = build_registry("mock", None, connections)["WS"]
    ctx = {"ws_message": {"type": "ALARM_NEW"}} if has_message else {}
    result = await notifier.send("family01", "告警", "请确认", ctx)
    assert result == NotifyResult(False, "WS", {"reason": "ws_unavailable"})
    assert connections.broadcast_to_user.await_count == int(has_message)


async def test_inbox_propagates_transaction_failure_for_retry():
    sessions = MagicMock()
    transaction = sessions.begin.return_value
    session = transaction.__aenter__.return_value = Mock()
    transaction.__aexit__.side_effect = OSError("commit failed")
    notifier = build_registry("mock", sessions, None)["INBOX"]
    with pytest.raises(OSError, match="commit failed"):
        await notifier.send("family01", "告警", "请确认", {"alarm_id": "a1"})
    stored = session.add.call_args.args[0]
    assert (stored.user_id, stored.biz_id, stored.type) == ("family01", "a1", "ALARM")
