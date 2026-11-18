from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import ColumnElement

from app.core.exceptions import BizException
from app.models import Alarm, Community, Device, Elder, Event, FamilyBinding, Guardian, User
from app.models.enums import DeviceStatus, ElderStatus, RoleCode
from app.schemas.records import CHINA, ElderFilters
from app.services.records import device_fields, mask_phone, resolve_directory_id


def summary_query():
    online = (
        select(Device.id)
        .where(Device.elder_id == Elder.id, Device.status == DeviceStatus.ONLINE)
        .exists()
    )
    now = datetime.now(UTC)
    recent_alarms = (
        select(func.count())
        .select_from(Alarm)
        .where(Alarm.elder_id == Elder.id, Alarm.created_at.between(now - timedelta(days=30), now))
        .scalar_subquery()
    )
    return (
        select(Elder, Community.name, Guardian.name, online, recent_alarms)
        .join(Community, Community.id == Elder.community_id)
        .outerjoin(Guardian, Guardian.id == Elder.guardian_id)
    )


def elder_fields(
    elder: Elder,
    community_name: str,
    guardian_name: str | None,
    device_online: bool,
    alarm_count: int,
    *,
    full_phone: bool = False,
) -> dict:
    today = datetime.now(CHINA).date()
    birth = elder.birth_date
    age = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
    return {
        "id": elder.id,
        "name": elder.name,
        "gender": elder.gender,
        "age": age,
        "birthDate": birth,
        "phone": elder.phone if full_phone else mask_phone(elder.phone),
        "address": elder.address,
        "roomNo": elder.room_no,
        "communityId": elder.community_id,
        "communityName": community_name,
        "guardianId": elder.guardian_id,
        "guardianName": guardian_name,
        "healthTags": elder.health_tags,
        "detectMode": elder.detect_mode,
        "status": elder.status,
        "deviceOnline": device_online,
        "alarmCount30d": alarm_count,
        "createdAt": elder.created_at,
    }


async def list_elders(
    db: AsyncSession, query: ElderFilters, scope: ColumnElement[bool] | None
) -> tuple[list[dict], int]:
    filters = [
        Elder.status != ElderStatus.PAUSED if query.status is None else Elder.status == query.status
    ]
    if scope is not None:
        filters.append(scope)
    if query.keyword:
        filters.append(
            or_(
                Elder.name.icontains(query.keyword, autoescape=True),
                Elder.room_no.icontains(query.keyword, autoescape=True),
                Elder.address.icontains(query.keyword, autoescape=True),
            )
        )
    if query.community_id:
        filters.append(
            Elder.community_id == await resolve_directory_id(db, Community, query.community_id)
        )
    if query.guardian_id:
        filters.append(
            Elder.guardian_id == await resolve_directory_id(db, Guardian, query.guardian_id)
        )
    total = await db.scalar(select(func.count()).select_from(Elder).where(*filters))
    rows = await db.execute(
        summary_query()
        .where(*filters)
        .order_by(Elder.created_at.desc(), Elder.id)
        .offset((query.page - 1) * query.page_size)
        .limit(query.page_size)
    )
    return [elder_fields(*row) for row in rows], total or 0


async def find_elder(
    db: AsyncSession, elder_id: str, scope: ColumnElement[bool] | None, *, lock: bool = False
) -> Elder:
    statement = select(Elder).where(Elder.id == elder_id)
    if scope is not None:
        statement = statement.where(scope)
    if lock:
        statement = statement.with_for_update()
    elder = await db.scalar(statement)
    if elder is None:
        raise BizException(1004, "老人档案不存在")
    return elder


def binding_fields(binding: FamilyBinding, family: User) -> dict:
    return {
        "bindingId": binding.id,
        "userId": family.id,
        "name": family.nickname,
        "phone": mask_phone(family.phone),
        "relation": binding.relation,
        "isPrimary": binding.is_primary,
        "notifyOrder": binding.notify_order,
    }


async def list_bindings(db: AsyncSession, elder_id: str) -> list[dict]:
    rows = await db.execute(
        select(FamilyBinding, User)
        .join(User, User.id == FamilyBinding.user_id)
        .where(FamilyBinding.elder_id == elder_id)
        .order_by(FamilyBinding.notify_order, FamilyBinding.id)
    )
    return [binding_fields(binding, family) for binding, family in rows]


async def recent_events(db: AsyncSession, elder: Elder) -> list[dict]:
    rows = await db.execute(
        select(Event, Device.device_no)
        .join(Device, Device.id == Event.device_id)
        .where(Event.elder_id == elder.id)
        .order_by(Event.occurred_at.desc(), Event.id)
        .limit(5)
    )
    return [
        {
            "id": event.id,
            "eventId": event.event_id,
            "elderId": elder.id,
            "elderName": elder.name,
            "roomNo": elder.room_no,
            "deviceId": event.device_id,
            "deviceNo": device_no,
            "type": event.type,
            "level": event.level,
            "confidence": float(event.confidence),
            "occurredAt": event.occurred_at,
            "snapshotUrl": event.snapshot_url,
            "clipUrl": event.clip_url,
            "handled": event.handled,
            "handleResult": event.handle_result,
        }
        for event, device_no in rows
    ]


async def elder_detail(
    db: AsyncSession, elder_id: str, scope: ColumnElement[bool] | None, *, full_phone: bool
) -> dict:
    statement = summary_query().where(Elder.id == elder_id)
    if scope is not None:
        statement = statement.where(scope)
    row = (await db.execute(statement)).one_or_none()
    if row is None:
        raise BizException(1004, "老人档案不存在")
    elder = row[0]
    device = await db.scalar(
        select(Device)
        .where(Device.elder_id == elder.id)
        .order_by(Device.created_at, Device.id)
        .limit(1)
    )
    return {
        **elder_fields(*row, full_phone=full_phone),
        "emergencyContact": elder.emergency_contact,
        "device": device_fields(device, elder.name) if device else None,
        "recentEvents": await recent_events(db, elder),
        "familyBindings": await list_bindings(db, elder.id),
    }


async def create_elder(db: AsyncSession, fields: dict, actor: User) -> Elder:
    community_id = await resolve_directory_id(db, Community, fields["community_id"])
    if await db.get(Community, community_id) is None:
        raise BizException(1004, "社区不存在")
    if actor.role_code != RoleCode.ADMIN and community_id != actor.community_id:
        raise BizException(1003, "无权限在该社区新增老人")
    guardian_id = await resolve_directory_id(db, Guardian, fields["guardian_id"])
    guardian = await db.get(Guardian, guardian_id)
    if guardian is None:
        raise BizException(1004, "网格员不存在")
    if guardian.community_id != community_id:
        raise BizException(1001, "网格员与老人须属于同一社区")
    fields.update(community_id=community_id, guardian_id=guardian_id)
    elder = Elder(id=uuid4().hex, **fields)
    db.add(elder)
    await db.flush()
    return elder


async def add_binding(db: AsyncSession, elder_id: str, fields: dict) -> dict:
    family = await db.get(User, fields["user_id"])
    if family is None:
        raise BizException(1004, "用户不存在")
    if family.role_code != RoleCode.FAMILY:
        raise BizException(1001, "绑定对象须为家属账号")
    statement = (
        insert(FamilyBinding)
        .values(id=uuid4().hex, elder_id=elder_id, **fields)
        .on_conflict_do_nothing(index_elements=[FamilyBinding.elder_id, FamilyBinding.user_id])
        .returning(FamilyBinding)
    )
    binding = await db.scalar(statement)
    if binding is None:
        raise BizException(1005, "家属已绑定该老人")
    return binding_fields(binding, family)
