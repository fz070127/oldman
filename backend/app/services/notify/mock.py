import structlog

from app.services.notify.base import Notifier, NotifyResult

log = structlog.get_logger()


class MockNotifier(Notifier):
    def __init__(self, channel: str):
        self.channel = channel

    async def send(self, to: str, title: str, content: str, ctx: dict) -> NotifyResult:
        log.info(
            "alarm_notify_mock",
            channel=self.channel,
            alarm_id=ctx["alarm_id"],
            user_id=ctx["user_id"],
            step=ctx["step"],
        )
        return NotifyResult(True, self.channel, {"provider": "mock"})


class UnconfiguredNotifier(Notifier):
    provider: str

    async def send(self, to: str, title: str, content: str, ctx: dict) -> NotifyResult:
        log.warning(
            "alarm_notify_provider_unconfigured", channel=self.channel, provider=self.provider
        )
        return await MockNotifier(self.channel).send(to, title, content, ctx)
