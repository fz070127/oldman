import asyncio
from datetime import UTC, datetime

import structlog
from pydantic import AwareDatetime, BaseModel, Field, StrictBool, ValidationError
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.exceptions import BizException
from app.models import Device
from app.mqtt.publisher import Command, MqttPublisher
from app.schemas.events import IngestPayload
from app.schemas.records import NO_NUL
from app.services.event_service import ingest

log = structlog.get_logger()


class Heartbeat(BaseModel):
    device_no: str | None = Field(default=None, alias="deviceNo")
    fps: float = Field(ge=0, allow_inf_nan=False)
    cpu: float = Field(ge=0, le=100)
    mem: float = Field(ge=0, le=100)
    ts: AwareDatetime


class CommandReply(BaseModel):
    cmd: Command
    ok: StrictBool
    msg: str = Field(default="", pattern=NO_NUL)


class MqttHandlers:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        redis: Redis,
        publisher: MqttPublisher,
    ):
        self.sessions = sessions
        self.redis = redis
        self.publisher = publisher

    async def on_heartbeat(self, device_no: str, raw: bytes) -> None:
        try:
            heartbeat = Heartbeat.model_validate_json(raw)
        except ValidationError:
            log.warning("mqtt_invalid_heartbeat", device_no=device_no)
            return
        if heartbeat.device_no is not None and heartbeat.device_no != device_no:
            log.warning("mqtt_heartbeat_device_mismatch", device_no=device_no)
            return

        received_at = datetime.now(UTC)
        async with self.sessions.begin() as db:
            device = await db.scalar(
                select(Device).where(Device.device_no == device_no).with_for_update()
            )
            if device is None:
                log.warning("mqtt_unknown_device", device_no=device_no)
                return
            was_offline = device.status != 1
            device.status = 1
            device.last_heartbeat = received_at
        if was_offline:
            # M7 will replace this placeholder with the WebSocket broadcast.
            log.info("DEVICE_STATUS", device_no=device_no, status=1)

        key = f"device:health:{device_no}"
        try:
            async with asyncio.timeout(1), self.redis.pipeline(transaction=True) as pipe:
                pipe.hset(
                    key, mapping={"fps": heartbeat.fps, "cpu": heartbeat.cpu, "mem": heartbeat.mem}
                )
                pipe.expire(key, 300)
                await pipe.execute()
        except (RedisError, OSError) as exc:
            log.warning(
                "mqtt_heartbeat_redis_degraded", device_no=device_no, error_type=type(exc).__name__
            )

    async def on_event(self, device_no: str, raw: bytes) -> None:
        try:
            payload = IngestPayload.model_validate_json(raw)
        except ValidationError:
            log.warning("mqtt_invalid_event", device_no=device_no)
            return
        if payload.device_no != device_no:
            log.warning(
                "mqtt_event_device_mismatch", device_no=device_no, event_id=payload.event_id
            )
            return
        async with self.sessions() as db:
            try:
                await ingest(db, payload, redis=self.redis)
            except BizException as exc:
                log.warning(
                    "mqtt_event_rejected",
                    device_no=device_no,
                    event_id=payload.event_id,
                    code=exc.code,
                )

    async def on_cmd_reply(self, device_no: str, raw: bytes) -> None:
        try:
            reply = CommandReply.model_validate_json(raw)
        except ValidationError:
            log.warning("mqtt_invalid_command_reply", device_no=device_no)
            return
        await self.publisher.confirm(device_no, reply.cmd, reply.ok, reply.msg)
