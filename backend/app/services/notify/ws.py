from app.models.enums import Channel
from app.services.notify.base import Notifier, NotifyResult


async def broadcast_to_user(user_id: str, msg: dict) -> bool:
    # M7 will connect this entry point to the WebSocket connection manager.
    return False


class WsNotifier(Notifier):
    channel = Channel.WS

    async def send(self, to: str, title: str, content: str, ctx: dict) -> NotifyResult:
        sent = await broadcast_to_user(
            to,
            {"alarmId": ctx["alarm_id"], "step": ctx["step"], "title": title, "content": content},
        )
        return NotifyResult(sent, self.channel, {} if sent else {"reason": "ws_unavailable"})
