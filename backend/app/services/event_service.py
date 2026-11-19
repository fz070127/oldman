from asyncio import timeout
from datetime import UTC, datetime
from uuid import uuid4

import structlog
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.exceptions import BizException
from app.models import Alarm, AlarmAction, Device, Elder, Event, FamilyBinding, User
from app.models.enums import Action, AlarmStatus, Channel
from app.schemas.events import IngestPayload
from app.services.audit_service import AuditService
from app.services.event_queries import scoped
from app.services.notify import dispatcher
from app.services.records import commit_and_audit

log = structlog.get_logger()
DEDUP_SECONDS = 300
OPEN_FOR_DEDUP = (AlarmStatus.PENDING, AlarmStatus.ACKNOWLEDGED, AlarmStatus.ESCALATED)


async def source(db, payload, scope):
    # Keep device assignment stable and serialize different devices reporting for one elder.
    devices = select(Device).where(Device.device_no == payload.device_no)
    if scope is not None:
        devices = devices.join(Elder).where(scope)
    device = await db.scalar(
        devices.with_for_update(of=Device).execution_options(populate_existing=True)
    )
    if device is None:
        raise BizException(1004, "设备不存在")
    if device.elder_id is None:
        raise BizException(1005, "设备未绑定老人")
    elder = await db.scalar(
        scoped(select(Elder).where(Elder.id == device.elder_id), scope).with_for_update()
    )
    if elder is None:
        raise BizException(1003, "无权限")
    if payload.elder_id is not None and payload.elder_id != elder.id:
        raise BizException(1005, "设备与老人绑定不一致")
    return device, elder


async def is_duplicate(db, redis, event, alarm_id):
    key = f"alarm:dedup:{event.elder_id}:{event.type}"
    try:
        async with timeout(1):
            # SET NX GET atomically returns the previous reservation, including on an NX miss.
            owner = await redis.set(key, alarm_id, nx=True, ex=DEDUP_SECONDS, get=True)
        if owner is None:
            return False
        owner_id = owner.decode() if isinstance(owner, bytes) else owner
        committed = await db.scalar(
            select(Alarm.id).where(Alarm.id == owner_id, Alarm.elder_id == event.elder_id)
        )
        if committed:
            return True
        # The previous SQL transaction rolled back. The elder lock fences replacement writers.
        async with timeout(1):
            await redis.set(key, alarm_id, ex=DEDUP_SECONDS)
    except (RedisError, OSError) as exc:
        log.warning("alarm_redis_degraded", elder_id=event.elder_id, error_type=type(exc).__name__)
    return False


async def record_alarm(db, redis, event):
    alarm_id = uuid4().hex
    if await is_duplicate(db, redis, event, alarm_id):
        recent = await db.scalar(
            select(Alarm.id)
            .join(Event, Event.id == Alarm.event_id)
            .where(
                Alarm.elder_id == event.elder_id,
                Event.type == event.type,
                Alarm.status.in_(OPEN_FOR_DEDUP),
            )
            .order_by(Alarm.created_at.desc(), Alarm.id.desc())
            .limit(1)
            .with_for_update(of=Alarm)
        )
        if recent:
            db.add(
                AlarmAction(
                    alarm_id=recent,
                    actor_id="SYSTEM",
                    action=Action.DEDUP,
                    detail={"eventId": event.event_id},
                    created_at=datetime.now(UTC),
                )
            )
        return None

    recipient = (
        await db.execute(
            select(User.id, User.nickname)
            .join(FamilyBinding, FamilyBinding.user_id == User.id)
            .where(FamilyBinding.elder_id == event.elder_id, User.status == 1)
            .order_by(FamilyBinding.is_primary.desc(), FamilyBinding.notify_order, User.id)
            .limit(1)
        )
    ).one_or_none()
    now = datetime.now(UTC)
    alarm = Alarm(
        id=alarm_id,
        event_id=event.id,
        elder_id=event.elder_id,
        level=event.level,
        status=AlarmStatus.PENDING,
        escalate_step=0,
        notified_at=now,
        created_at=now,
        current_handler=recipient.id if recipient else None,
    )
    db.add(alarm)
    await db.flush()
    db.add(
        AlarmAction(
            alarm_id=alarm.id,
            actor_id="SYSTEM",
            action=Action.NOTIFY,
            channel=Channel.PUSH,
            result="SENT",
            created_at=now,
            detail={"to": recipient.id, "toName": recipient.nickname} if recipient else {},
        )
    )
    await db.flush()
    await dispatcher.notify_new_alarm(alarm)
    return alarm


async def ingest(
    db: AsyncSession,
    payload: IngestPayload | dict,
    *,
    redis: Redis | None = None,
    scope=None,
    actor_id="SYSTEM",
    audit: AuditService | None = None,
) -> tuple[Event, Alarm | None]:
    """Own one unit of work on a dedicated session (expire_on_commit=False)."""
    payload = IngestPayload.model_validate(payload)
    try:
        device, elder = await source(db, payload, scope)
        values = payload.model_dump(exclude={"elder_id", "device_no"})
        statement = (
            insert(Event)
            .values(id=uuid4().hex, device_id=device.id, elder_id=elder.id, **values)
            .on_conflict_do_nothing(index_elements=[Event.event_id])
            .returning(Event)
        )
        event = await db.scalar(statement)
        if event is None:
            existing = scoped(
                select(Event, Alarm)
                .join(Elder, Elder.id == Event.elder_id)
                .outerjoin(Alarm, Alarm.event_id == Event.id)
                .where(Event.event_id == payload.event_id),
                scope,
            )
            row = (await db.execute(existing)).one_or_none()
            if row is None:
                raise BizException(1003, "无权限")
            await db.commit()
            return row.Event, row.Alarm

        alarm = None
        if event.level in ("P0", "P1"):
            if redis is None:
                async with Redis.from_url(Settings().redis_url) as client:
                    alarm = await record_alarm(db, client, event)
            else:
                alarm = await record_alarm(db, redis, event)
        if audit is None:
            audit = AuditService(async_sessionmaker(db.bind))
        await commit_and_audit(
            db,
            audit,
            actor_id,
            "INGEST_EVENT",
            event.id,
            {"event_id": event.event_id, "level": event.level},
        )
        return event, alarm
    except BaseException:
        await db.rollback()
        raise
