from datetime import datetime, timedelta

from sqlalchemy import Date, Float, Integer, Numeric, case, cast, extract, func, select, true
from sqlalchemy.dialects.postgresql import JSONB, aggregate_order_by

from app.models import Alarm, Community, Device, Elder, Event
from app.models.enums import AlarmStatus, DeviceStatus, ElderStatus, HandleResult
from app.schemas.records import CHINA
from app.services.device_presence import HEARTBEAT_TTL
from app.services.event_queries import scoped


def today_at(now: datetime) -> datetime:
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def online_device():
    return Device.last_heartbeat > func.now() - HEARTBEAT_TTL


def ratio(numerator, denominator):
    fraction = cast(numerator, Numeric) / func.nullif(denominator, 0)
    return cast(func.coalesce(func.round(fraction, 2), 0), Float)


async def overview(db, scope) -> dict:
    now = datetime.now(CHINA)
    today = today_at(now)
    count = func.count()
    elder_online = select(Device.id).where(Device.elder_id == Elder.id, online_device()).exists()
    elders = scoped(
        select(count.label("elderTotal"), count.filter(elder_online).label("elderOnline"))
        .select_from(Elder)
        .where(Elder.status != ElderStatus.DECEASED),
        scope,
    ).cte()
    devices = scoped(
        select(count.label("deviceTotal"), count.filter(online_device()).label("deviceOnline"))
        .select_from(Device)
        .outerjoin(Elder),
        scope,
    ).cte()
    alarms = scoped(
        select(
            count.filter(Alarm.created_at >= today).label("alarmToday"),
            count.filter(Alarm.status == AlarmStatus.PENDING).label("alarmPending"),
            count.filter(Alarm.created_at >= today, Alarm.level == "P0").label("alarmP0Today"),
            cast(
                func.coalesce(
                    func.round(
                        func.avg(extract("epoch", Alarm.ack_at - Alarm.notified_at)).filter(
                            Alarm.created_at >= now - timedelta(hours=24)
                        )
                    ),
                    0,
                ),
                Integer,
            ).label("avgResponseSec"),
        )
        .select_from(Alarm)
        .join(Elder),
        scope,
    ).cte()
    events = scoped(
        select(
            ratio(count.filter(Event.handle_result == HandleResult.FALSE_POSITIVE), count).label(
                "falsePositiveRate"
            )
        )
        .select_from(Event)
        .join(Elder)
        .where(Event.handled.is_(True)),
        scope,
    ).cte()
    statement = select(
        elders,
        devices,
        (devices.c.deviceTotal - devices.c.deviceOnline).label("deviceOffline"),
        alarms,
        events,
    ).select_from(elders.join(devices, true()).join(alarms, true()).join(events, true()))
    return {**(await db.execute(statement)).mappings().one(), "updatedAt": now}


async def trend(db, scope, days: int) -> list[dict]:
    today = today_at(datetime.now(CHINA))
    offsets = func.generate_series(0, days - 1).table_valued("day_offset").render_derived()
    dates = select((cast(today.date(), Date) - offsets.c.day_offset).label("date")).cte()
    day = cast(func.timezone(today.utcoffset(), Alarm.created_at), Date)
    levels = ("p0", "p1", "p2")
    totals = (
        scoped(
            select(
                day.label("date"),
                *(
                    func.count().filter(Alarm.level == level.upper()).label(level)
                    for level in levels
                ),
                func.count().label("total"),
            )
            .select_from(Alarm)
            .join(Elder)
            .where(
                Alarm.created_at >= today - timedelta(days=days - 1),
                Alarm.created_at < today + timedelta(days=1),
            ),
            scope,
        )
        .group_by(day)
        .cte()
    )
    statement = (
        select(
            dates.c.date,
            *(func.coalesce(totals.c[key], 0).label(key) for key in (*levels, "total")),
        )
        .select_from(dates.outerjoin(totals, dates.c.date == totals.c.date))
        .order_by(dates.c.date)
    )
    return [dict(row) for row in (await db.execute(statement)).mappings()]


async def distribution(db, scope, community_scope) -> list[dict]:
    today = today_at(datetime.now(CHINA))
    by_elders = (
        scoped(
            select(Elder.community_id, func.count().label("total")).where(
                Elder.status != ElderStatus.DECEASED
            ),
            scope,
        )
        .group_by(Elder.community_id)
        .cte()
    )
    by_alarms = (
        scoped(
            select(Elder.community_id, func.count().label("total"))
            .select_from(Alarm)
            .join(Elder)
            .where(Alarm.created_at >= today),
            scope,
        )
        .group_by(Elder.community_id)
        .cte()
    )
    coordinates = func.decode(func.md5(Community.id), "hex")
    statement = scoped(
        select(
            Community.id.label("communityId"),
            Community.name.label("communityName"),
            func.coalesce(by_elders.c.total, 0).label("elderTotal"),
            func.coalesce(by_alarms.c.total, 0).label("alarmToday"),
            (0.1 + 0.8 * func.get_byte(coordinates, 0) / 255.0).label("x"),
            (0.1 + 0.8 * func.get_byte(coordinates, 1) / 255.0).label("y"),
        )
        .outerjoin(by_elders, by_elders.c.community_id == Community.id)
        .outerjoin(by_alarms, by_alarms.c.community_id == Community.id),
        community_scope,
    ).order_by(Community.id)
    return [dict(row) for row in (await db.execute(statement)).mappings()]


async def realtime(db, scope) -> list[dict]:
    statement = (
        scoped(
            select(
                Event.id,
                Elder.id.label("elderId"),
                Elder.name.label("elderName"),
                Community.id.label("communityId"),
                Community.name.label("communityName"),
                Elder.room_no.label("roomNo"),
                Event.type,
                Event.level,
                cast(Event.confidence, Float).label("confidence"),
                Event.occurred_at.label("occurredAt"),
                Event.snapshot_url.label("snapshotUrl"),
            )
            .select_from(Event)
            .join(Elder)
            .join(Community),
            scope,
        )
        .order_by(Event.occurred_at.desc(), Event.id.desc())
        .limit(20)
    )
    return [dict(row) for row in (await db.execute(statement)).mappings()]


async def device_status(db, scope) -> dict:
    status = case(
        (online_device(), DeviceStatus.ONLINE),
        (Device.status == DeviceStatus.ONLINE, DeviceStatus.OFFLINE),
        else_=Device.status,
    )
    devices = scoped(
        select(
            Device.id,
            Device.device_no,
            Device.elder_id,
            Elder.name.label("elder_name"),
            Community.name.label("community_name"),
            Elder.room_no,
            status.label("status"),
            Device.last_heartbeat,
        )
        .select_from(Device)
        .outerjoin(Elder)
        .outerjoin(Community),
        scope,
    ).cte()
    fields = devices.c
    count = func.count()
    online = count.filter(fields.status == DeviceStatus.ONLINE)
    item = func.jsonb_build_object(
        "id",
        fields.id,
        "deviceNo",
        fields.device_no,
        "elderId",
        fields.elder_id,
        "elderName",
        fields.elder_name,
        "communityName",
        fields.community_name,
        "roomNo",
        fields.room_no,
        "status",
        fields.status,
        "lastHeartbeat",
        fields.last_heartbeat,
    )
    offline_list = func.jsonb_agg(aggregate_order_by(item, fields.device_no), type_=JSONB).filter(
        fields.status != DeviceStatus.ONLINE
    )
    statement = select(
        count.label("total"),
        online.label("online"),
        count.filter(fields.status == DeviceStatus.OFFLINE).label("offline"),
        count.filter(fields.status == DeviceStatus.FAULT).label("fault"),
        count.filter(fields.status == DeviceStatus.INACTIVE).label("inactive"),
        ratio(online, count).label("onlineRate"),
        func.coalesce(offline_list, func.jsonb_build_array()).label("offlineList"),
    )
    return dict((await db.execute(statement)).mappings().one())
