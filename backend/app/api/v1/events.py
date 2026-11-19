from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request
from sqlalchemy import select

from app.core.deps import Audit, DbSession, UserScope, require_permission
from app.core.exceptions import BizException
from app.core.response import R
from app.models import Device, Elder, User
from app.schemas.events import EventFilters, Handle, IngestPayload, MockEvent, StatsRange
from app.schemas.records import RecordId
from app.services import alarm_service, event_queries, event_service
from app.services.records import commit_and_audit

router = APIRouter(prefix="/events", tags=["事件"])
mock_router = APIRouter(prefix="/events", tags=["事件"])
read_event = Depends(require_permission("event:read"))
EventWriter = Annotated[User, Depends(require_permission("event:write"))]
EventId = Annotated[RecordId, Path(alias="id")]


@router.get("", dependencies=[read_event])
async def list_events(query: Annotated[EventFilters, Query()], scope: UserScope, db: DbSession):
    items, total = await event_queries.list_events(db, query, scope)
    return R.page(items, total, query.page, query.page_size)


@router.get("/stats", dependencies=[read_event])
async def stats(db: DbSession, scope: UserScope, range: StatsRange = "7d"):
    return R.ok(await event_queries.event_stats(db, range, scope))


@router.get("/{id}", dependencies=[read_event])
async def get_event(event_id: EventId, db: DbSession, scope: UserScope):
    row = await event_queries.find_event(db, event_id, scope)
    return R.ok(event_queries.event_fields(*row, full=True))


@router.get("/{id}/media", dependencies=[read_event])
async def get_media(event_id: EventId, db: DbSession, scope: UserScope):
    event, _, _ = await event_queries.find_event(db, event_id, scope)
    # TODO(M6): sign the stored media URLs and return their actual TTL.
    return R.ok(
        {
            "snapshotUrl": event.snapshot_url,
            "clipUrl": event.clip_url,
            "keyframes": [event.snapshot_url] if event.snapshot_url else [],
            "expiresInSec": 0,
        }
    )


@router.put("/{id}/handle")
async def handle_event(
    event_id: EventId,
    body: Handle,
    actor: EventWriter,
    db: DbSession,
    scope: UserScope,
    audit: Audit,
):
    row = await event_queries.find_event(db, event_id, scope, lock=True)
    event = row.Event
    event.handled, event.handle_result = True, body.result
    event.handle_remark, event.handled_at = body.remark, datetime.now(UTC)
    await commit_and_audit(db, audit, actor.id, "HANDLE_EVENT", event.id, body.model_dump())
    return R.ok(event_queries.event_fields(*row, full=True))


@mock_router.post("/mock")
async def mock_event(
    body: MockEvent,
    request: Request,
    actor: EventWriter,
    db: DbSession,
    scope: UserScope,
    audit: Audit,
):
    statement = (
        select(Device.device_no, Device.algo_version)
        .join(Elder)
        .where(Elder.id == body.elder_id)
        .order_by(Device.id)
        .limit(1)
    )
    device = (await db.execute(event_queries.scoped(statement, scope))).one_or_none()
    if device is None:
        raise BizException(1004, "老人没有已绑定的设备")
    payload = IngestPayload(
        **body.model_dump(), device_no=device.device_no, algo_version=device.algo_version
    )
    event, alarm = await event_service.ingest(
        db, payload, redis=request.app.state.redis, scope=scope, actor_id=actor.id, audit=audit
    )
    row = await event_queries.find_event(db, event.id, scope)
    alarm_data = None
    if alarm is not None:
        alarm_data = alarm_service.alarm_fields(
            *await alarm_service.find_alarm(db, alarm.id, scope)
        )
    return R.ok({"event": event_queries.event_fields(*row, full=True), "alarm": alarm_data})
