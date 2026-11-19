from app.models.enums import Channel
from app.services.notify.base import Notifier, NotifyResult
from app.ws.manager import ConnectionManager


class WsNotifier(Notifier):
    channel = Channel.WS

    def __init__(self, connections: ConnectionManager | None = None):
        self.connections = connections

    async def send(self, to: str, title: str, content: str, ctx: dict) -> NotifyResult:
        message = ctx.get("ws_message")
        count = (
            await self.connections.broadcast_to_user(to, message)
            if (self.connections is not None and message is not None)
            else 0
        )
        sent = count > 0
        return NotifyResult(sent, self.channel, {} if sent else {"reason": "ws_unavailable"})
