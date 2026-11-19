from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Notification
from app.models.enums import Channel
from app.services.notify.base import Notifier, NotifyResult


class InboxNotifier(Notifier):
    channel = Channel.INBOX

    def __init__(self, sessions: async_sessionmaker[AsyncSession]):
        self.sessions = sessions

    async def send(self, to: str, title: str, content: str, ctx: dict) -> NotifyResult:
        notification = Notification(
            id=uuid4().hex,
            user_id=to,
            type="ALARM",
            title=title,
            content=content,
            biz_id=ctx["alarm_id"],
        )
        async with self.sessions.begin() as db:
            db.add(notification)
        return NotifyResult(True, self.channel, {"notificationId": notification.id})
