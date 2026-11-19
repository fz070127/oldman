from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from app.core.deps import Audit, DbSession, UserScope, require_permission
from app.core.response import R
from app.models import User
from app.schemas.events import Ack, AlarmFilters, Dispatch, Resolve, StatsRange
from app.schemas.records import RecordId
from app.services import alarm_service
from app.services.records import commit_and_audit

router = APIRouter(prefix="/alarms", tags=["告警"])
read_alarm = Depends(require_permission("alarm:read"))
AlarmId = Annotated[RecordId, Path(alias="id")]


@router.get("", dependencies=[read_alarm])
async def list_alarms(query: Annotated[AlarmFilters, Query()], scope: UserScope, db: DbSession):
    items, total = await alarm_service.list_alarms(db, query, scope)
    return R.page(items, total, query.page, query.page_size)


@router.get("/pending-count", dependencies=[read_alarm])
async def pending_count(db: DbSession, scope: UserScope):
    return R.ok({"count": await alarm_service.pending_count(db, scope)})


@router.get("/stats", dependencies=[read_alarm])
async def stats(db: DbSession, scope: UserScope, range: StatsRange = "7d"):
    return R.ok(await alarm_service.alarm_stats(db, range, scope))


@router.get("/{id}", dependencies=[read_alarm])
async def get_alarm(alarm_id: AlarmId, db: DbSession, scope: UserScope):
    row = await alarm_service.find_alarm(db, alarm_id, scope)
    return R.ok(await alarm_service.alarm_detail(db, row, scope))


async def update_alarm(db, alarm_id, scope, actor, body, audit):
    row = await alarm_service.find_alarm(db, alarm_id, scope, lock=True)
    action = await alarm_service.apply_action(db, row, body, actor)
    # Rejoin the new handler before releasing the row lock.
    row = await alarm_service.find_alarm(db, alarm_id, scope)
    data = alarm_service.alarm_fields(*row)
    await commit_and_audit(db, audit, actor.id, action, alarm_id, body.model_dump())
    return R.ok(data)


@router.post("/{id}/ack")
async def ack(
    alarm_id: AlarmId,
    body: Ack,
    db: DbSession,
    scope: UserScope,
    audit: Audit,
    actor: Annotated[User, Depends(require_permission("alarm:ack"))],
):
    return await update_alarm(db, alarm_id, scope, actor, body, audit)


@router.post("/{id}/dispatch")
async def dispatch(
    alarm_id: AlarmId,
    body: Dispatch,
    db: DbSession,
    scope: UserScope,
    audit: Audit,
    actor: Annotated[User, Depends(require_permission("alarm:dispatch"))],
):
    return await update_alarm(db, alarm_id, scope, actor, body, audit)


@router.post("/{id}/resolve")
async def resolve(
    alarm_id: AlarmId,
    body: Resolve,
    db: DbSession,
    scope: UserScope,
    audit: Audit,
    actor: Annotated[User, Depends(require_permission("alarm:*"))],
):
    return await update_alarm(db, alarm_id, scope, actor, body, audit)
