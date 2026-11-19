from datetime import datetime, timedelta

from sqlalchemy import and_, func, select

from app.core.exceptions import BizException
from app.models import Device, Elder, Event
from app.schemas.events import EventFilters, Filters, StatsRange
from app.schemas.records import CHINA


def scoped(statement, scope):
    return statement.where(scope) if scope is not None else statement


def filtered(statement, query: Filters, model, timestamp, fields):
    for key in fields:
        value = getattr(query, key)
        if value is not None:
            statement = statement.where(getattr(model, key) == value)
    if query.start_time is not None:
        statement = statement.where(timestamp >= query.start_time)
    if query.end_time is not None:
        statement = statement.where(timestamp <= query.end_time)
    return statement


async def page_rows(db, statement, query, timestamp, record_id):
    count = await db.scalar(select(func.count()).select_from(statement.subquery()))
    rows = await db.execute(
        statement.order_by(timestamp.desc(), record_id)
        .offset((query.page - 1) * query.page_size)
        .limit(query.page_size)
    )
    return rows.all(), count


def period(span: StatsRange):
    now = datetime.now(CHINA)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start = today if span == "today" else now - timedelta(days={"7d": 7, "30d": 30}[span])
    return start, today, now


def event_query(scope):
    return scoped(
        select(Event, Elder, Device.device_no)
        .join(Elder, Elder.id == Event.elder_id)
        .join(Device, Device.id == Event.device_id),
        scope,
    )


def event_fields(event, elder, device_no, *, full=False):
    data = {
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
        "handleRemark": event.handle_remark,
        "handledAt": event.handled_at,
    }
    if full:
        data.update(features=event.features, algoVersion=event.algo_version)
    return data


async def find_event(db, event_id, scope, *, lock=False):
    statement = event_query(scope).where(Event.id == event_id)
    if lock:
        statement = statement.with_for_update(of=Event)
    row = (await db.execute(statement)).one_or_none()
    if row is None:
        raise BizException(1004, "事件不存在")
    return row


async def list_events(db, query: EventFilters, scope):
    statement = filtered(
        event_query(scope),
        query,
        Event,
        Event.occurred_at,
        ("elder_id", "device_id", "type", "level", "handled"),
    )
    rows, total = await page_rows(db, statement, query, Event.occurred_at, Event.id)
    return [event_fields(*row) for row in rows], total


async def event_stats(db, span, scope):
    start, today, now = period(span)
    count = func.count()
    row = (
        await db.execute(
            scoped(
                select(
                    count.label("total"),
                    count.filter(Event.handled).label("handled"),
                    count.filter(Event.handle_result == "FALSE_POSITIVE", Event.handled).label(
                        "fp"
                    ),
                    count.filter(Event.occurred_at >= today).label("today"),
                    count.filter(and_(Event.occurred_at >= today, Event.level == "P0")).label(
                        "today_p0"
                    ),
                    *(
                        count.filter(Event.level == level).label(level)
                        for level in ("P0", "P1", "P2")
                    ),
                    count.filter(Event.type == "FALL").label("fall"),
                    count.filter(Event.type == "LONG_LIE").label("long_lie"),
                )
                .select_from(Event)
                .join(Elder)
                .where(Event.occurred_at.between(start, now)),
                scope,
            )
        )
    ).one()
    return {
        "range": span,
        "total": row.total,
        "todayTotal": row.today,
        "todayP0": row.today_p0,
        "unhandledCount": row.total - row.handled,
        "falsePositiveCount": row.fp,
        "falsePositiveRate": round(row.fp / row.handled, 2) if row.handled else 0,
        "byLevel": {level.lower(): row._mapping[level] for level in ("P0", "P1", "P2")},
        "byType": {"fall": row.fall, "longLie": row.long_lie},
    }
