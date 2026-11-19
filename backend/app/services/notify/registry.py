from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.enums import Channel
from app.services.notify.base import Notifier
from app.services.notify.call import CallNotifier
from app.services.notify.inbox import InboxNotifier
from app.services.notify.mock import MockNotifier
from app.services.notify.push import PushNotifier
from app.services.notify.sms import SmsNotifier
from app.services.notify.ws import WsNotifier
from app.ws.manager import ConnectionManager


def build_registry(
    provider: str, sessions: async_sessionmaker[AsyncSession], connections: ConnectionManager | None
) -> dict[str, Notifier]:
    external = (
        (MockNotifier(Channel.PUSH), MockNotifier(Channel.SMS), MockNotifier(Channel.CALL))
        if provider == "mock"
        else (PushNotifier(), SmsNotifier(), CallNotifier())
    )
    return {
        notifier.channel: notifier
        for notifier in (*external, InboxNotifier(sessions), WsNotifier(connections))
    }
