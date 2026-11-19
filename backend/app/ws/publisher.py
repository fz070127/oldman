from datetime import datetime
from math import ceil

import structlog
from fastapi.encoders import jsonable_encoder
from sqlalchemy import and_, or_, select

from app.models import Community, Elder, FamilyBinding, Guardian, User
from app.models.enums import RoleCode
from app.schemas.records import CHINA

log = structlog.get_logger()


def envelope(kind: str, data: dict) -> dict:
    return {"type": kind, "ts": datetime.now(CHINA).isoformat(), "data": jsonable_encoder(data)}


def alarm_update(alarm, handler: str | None) -> dict:
    return envelope(
        "ALARM_UPDATE",
        {
            "alarmId": alarm.id,
            "status": alarm.status,
            "escalateStep": alarm.escalate_step,
            "currentHandler": handler,
        },
    )


class RealtimePublisher:
    def __init__(self, connections, sessions):
        self.connections = connections
        self.sessions = sessions

    async def new_alarm(self, alarm, event, elder, rules, *, exclude_user_id=None) -> dict | None:
        if not self.connections.all and exclude_user_id is None:
            return None
        try:
            async with self.sessions() as db:
                community_name = await db.scalar(
                    select(Community.name).where(Community.id == elder.community_id)
                )
            due = rules.due(alarm, 1)
            message = envelope(
                "ALARM_NEW",
                {
                    "alarmId": alarm.id,
                    "level": alarm.level,
                    "elderId": elder.id,
                    "elderName": elder.name,
                    "communityName": community_name,
                    "roomNo": elder.room_no,
                    "eventType": event.type,
                    "confidence": float(event.confidence),
                    "occurredAt": event.occurred_at,
                    "snapshotUrl": event.snapshot_url,
                    "remainingSec": max(0, ceil(due - datetime.now(CHINA).timestamp()))
                    if due is not None
                    else None,
                },
            )
        except Exception:
            log.exception("ws_new_alarm_failed", alarm_id=alarm.id)
            return None
        await self.alarm(alarm.elder_id, message, exclude_user_id=exclude_user_id)
        return message

    async def alarm(self, elder_id: str, message: dict, *, exclude_user_id: str | None = None):
        if not self.connections.all:
            return
        family = select(FamilyBinding.user_id).where(FamilyBinding.elder_id == Elder.id)
        guardian = select(Guardian.user_id).where(Guardian.id == Elder.guardian_id)
        statement = (
            select(Elder.community_id, User.id)
            .select_from(Elder)
            .outerjoin(
                User,
                and_(
                    User.status == 1,
                    or_(
                        and_(
                            User.role_code == RoleCode.FAMILY, User.id.in_(family.correlate(Elder))
                        ),
                        and_(
                            User.role_code == RoleCode.GUARDIAN,
                            User.id.in_(guardian.correlate(Elder)),
                        ),
                    ),
                ),
            )
            .where(Elder.id == elder_id)
        )
        try:
            async with self.sessions() as db:
                rows = (await db.execute(statement)).all()
            if rows:
                await self.connections.broadcast_scoped(
                    rows[0].community_id,
                    message,
                    user_ids=(user_id for _, user_id in rows if user_id is not None),
                    exclude_user_id=exclude_user_id,
                )
        except Exception:
            log.exception("ws_alarm_broadcast_failed", elder_id=elder_id)

    async def device(self, device, community_id: str | None) -> int:
        return await self.connections.broadcast_scoped(
            community_id,
            envelope(
                "DEVICE_STATUS",
                {
                    "deviceId": device.id,
                    "deviceNo": device.device_no,
                    "status": device.status,
                    "lastHeartbeat": device.last_heartbeat,
                },
            ),
        )
