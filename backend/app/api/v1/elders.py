from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy import delete

from app.core.deps import Audit, DbSession, UserScope, require_permission
from app.core.exceptions import BizException
from app.core.response import R
from app.models import FamilyBinding, User
from app.models.enums import ElderStatus, RoleCode
from app.schemas.records import (
    ElderCreate,
    ElderFilters,
    ElderUpdate,
    FamilyBindingCreate,
    RecordId,
)
from app.schemas.responses import (
    ElderDetail,
    ElderItem,
    ElderState,
    FamilyBindingItem,
    Page,
    Response,
)
from app.services import elder_service
from app.services.records import commit_and_audit

router = APIRouter(prefix="/elders", tags=["老人档案"])
read_elder = Depends(require_permission("elder:read"))
ElderReader = Annotated[User, read_elder]
ElderWriter = Annotated[User, Depends(require_permission("elder:write"))]
ElderId = Annotated[RecordId, Path(alias="id")]
BindingId = Annotated[RecordId, Path(alias="bindingId")]


@router.get("", dependencies=[read_elder], response_model=Response[Page[ElderItem]])
async def list_elders(
    query: Annotated[ElderFilters, Query()], scope: UserScope, db: DbSession
) -> dict:
    items, total = await elder_service.list_elders(db, query, scope)
    return R.page(items, total, query.page, query.page_size)


@router.get("/{id}", response_model=Response[ElderDetail])
async def get_elder(elder_id: ElderId, actor: ElderReader, scope: UserScope, db: DbSession) -> dict:
    full_phone = actor.role_code in (RoleCode.ADMIN, RoleCode.COMMUNITY_ADMIN)
    return R.ok(await elder_service.elder_detail(db, elder_id, scope, full_phone=full_phone))


@router.post("", status_code=201, response_model=Response[ElderDetail])
async def create_elder(body: ElderCreate, actor: ElderWriter, db: DbSession, audit: Audit) -> dict:
    fields = body.model_dump()
    elder = await elder_service.create_elder(db, fields, actor)
    result = await elder_service.elder_detail(db, elder.id, None, full_phone=True)
    await commit_and_audit(db, audit, actor.id, "CREATE_ELDER", elder.id, fields)
    return R.ok(result)


@router.put("/{id}", response_model=Response[ElderDetail])
async def update_elder(
    elder_id: ElderId,
    body: ElderUpdate,
    actor: ElderWriter,
    scope: UserScope,
    db: DbSession,
    audit: Audit,
) -> dict:
    elder = await elder_service.find_elder(db, elder_id, scope, lock=True)
    changes = {
        key: value
        for key, value in body.model_dump(exclude_unset=True).items()
        if value != getattr(elder, key)
    }
    for key, value in changes.items():
        setattr(elder, key, value)
    result = await elder_service.elder_detail(db, elder_id, scope, full_phone=True)
    await commit_and_audit(db, audit, actor.id, "UPDATE_ELDER", elder_id, changes)
    return R.ok(result)


@router.delete("/{id}", response_model=Response[ElderState])
async def disable_elder(
    elder_id: ElderId, actor: ElderWriter, scope: UserScope, db: DbSession, audit: Audit
) -> dict:
    elder = await elder_service.find_elder(db, elder_id, scope, lock=True)
    elder.status = ElderStatus.PAUSED
    await commit_and_audit(db, audit, actor.id, "DELETE_ELDER", elder_id, {"status": elder.status})
    return R.ok({"id": elder_id, "status": elder.status})


@router.get(
    "/{id}/bindings", dependencies=[read_elder], response_model=Response[list[FamilyBindingItem]]
)
async def list_bindings(elder_id: ElderId, scope: UserScope, db: DbSession) -> dict:
    await elder_service.find_elder(db, elder_id, scope)
    return R.ok(await elder_service.list_bindings(db, elder_id))


@router.post("/{id}/bindings", status_code=201, response_model=Response[FamilyBindingItem])
async def add_binding(
    elder_id: ElderId,
    body: FamilyBindingCreate,
    actor: ElderWriter,
    scope: UserScope,
    db: DbSession,
    audit: Audit,
) -> dict:
    await elder_service.find_elder(db, elder_id, scope)
    result = await elder_service.add_binding(db, elder_id, body.model_dump())
    changes = {"familyBinding": {"operation": "add", **result}}
    await commit_and_audit(db, audit, actor.id, "UPDATE_ELDER", elder_id, changes)
    return R.ok(result)


@router.delete("/{id}/bindings/{bindingId}", response_model=Response[None])
async def remove_binding(
    elder_id: ElderId,
    binding_id: BindingId,
    actor: ElderWriter,
    scope: UserScope,
    db: DbSession,
    audit: Audit,
) -> dict:
    await elder_service.find_elder(db, elder_id, scope)
    removed = await db.scalar(
        delete(FamilyBinding)
        .where(FamilyBinding.id == binding_id, FamilyBinding.elder_id == elder_id)
        .returning(FamilyBinding.user_id)
    )
    if removed is None:
        raise BizException(1004, "家属绑定不存在")
    changes = {"familyBinding": {"operation": "remove", "bindingId": binding_id, "userId": removed}}
    await commit_and_audit(db, audit, actor.id, "UPDATE_ELDER", elder_id, changes)
    return R.ok()
