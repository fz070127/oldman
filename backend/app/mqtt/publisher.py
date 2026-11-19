import asyncio
import json
from dataclasses import dataclass
from typing import Literal
from uuid import uuid4

import aiomqtt
import structlog
from sqlalchemy import func, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import MqttCmdLog
from app.mqtt.client import MqttClient, valid_device_no

log = structlog.get_logger()
Command = Literal["config.reload", "capture", "restart"]


@dataclass
class PendingCommand:
    id: str
    reply: asyncio.Future[bool]


class MqttPublisher:
    def __init__(self, mqtt: MqttClient, sessions: async_sessionmaker[AsyncSession]):
        self.mqtt = mqtt
        self.sessions = sessions
        self.pending: dict[tuple[str, Command], PendingCommand] = {}

    async def publish_cmd(
        self, device_no: str, cmd: Command, payload: dict, timeout: float = 5
    ) -> bool:
        key = device_no, cmd
        if not valid_device_no(device_no) or key in self.pending:
            return False
        message = json.dumps({"cmd": cmd, "payload": payload}, allow_nan=False)
        pending = PendingCommand(uuid4().hex, asyncio.get_running_loop().create_future())
        self.pending[key] = pending
        try:
            async with self.sessions.begin() as db:
                db.add(
                    MqttCmdLog(
                        id=pending.id,
                        device_no=device_no,
                        cmd=cmd,
                        payload=payload,
                        status="PENDING",
                    )
                )
            try:
                async with asyncio.timeout(timeout):
                    await self.mqtt.publish(f"edge/{device_no}/cmd", message)
                    return await pending.reply
            except TimeoutError:
                await self._finish(pending.id, "TIMEOUT")
            except (aiomqtt.MqttError, OSError) as exc:
                log.warning(
                    "mqtt_command_publish_failed", device_no=device_no, cmd=cmd, error=str(exc)
                )
                await self._finish(pending.id, "PUBLISH_FAILED")
            except asyncio.CancelledError:
                await self._finish(pending.id, "CANCELLED")
                raise
            return False
        finally:
            self.pending.pop(key)
            pending.reply.cancel()

    async def confirm(self, device_no: str, cmd: Command, ok: bool, msg: str) -> None:
        pending = self.pending.get((device_no, cmd))
        if pending is None or pending.reply.done():
            return
        status = "ACKNOWLEDGED" if ok else "REJECTED"
        finished = await self._finish(pending.id, status, msg)
        if finished and not pending.reply.done():
            pending.reply.set_result(ok)

    async def _finish(self, command_id: str, status: str, msg: str | None = None) -> bool:
        async with self.sessions.begin() as db:
            result = await db.scalar(
                update(MqttCmdLog)
                .where(MqttCmdLog.id == command_id, MqttCmdLog.status == "PENDING")
                .values(status=status, reply_message=msg, completed_at=func.now())
                .returning(MqttCmdLog.id)
            )
        return result is not None
