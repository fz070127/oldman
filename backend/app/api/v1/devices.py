from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request

from app.core.deps import Audit, DbSession, UserScope, require_permission
from app.core.exceptions import BizException
from app.core.response import R
from app.models import User
from app.schemas.records import DeviceCreate, DeviceFilters, DeviceUpdate, RecordId
from app.schemas.responses import (
    DeviceDetail,
    DeviceItem,
    Page,
    Response,
)
from app.services import device_service
from app.services.records import commit_and_audit

router = APIRouter(prefix="/devices", tags=["设备"])
read_device = Depends(require_permission("device:read"))
DeviceWriter = Annotated[User, Depends(require_permission("device:write"))]
DeviceId = Annotated[RecordId, Path(alias="id")]


@router.get("", dependencies=[read_device], response_model=Response[Page[DeviceItem]])
async def list_devices(
    query: Annotated[DeviceFilters, Query()], scope: UserScope, db: DbSession
) -> dict:
    items, total = await device_service.list_devices(db, query, scope)
    return R.page(items, total, query.page, query.page_size)


@router.get("/{id}", dependencies=[read_device], response_model=Response[DeviceDetail])
async def get_device(device_id: DeviceId, scope: UserScope, db: DbSession) -> dict:
    device, elder = await device_service.find_device(db, device_id, scope)
    return R.ok(device_service.device_detail(device, elder))


@router.post("", status_code=201, response_model=Response[DeviceDetail])
async def create_device(
    body: DeviceCreate, actor: DeviceWriter, scope: UserScope, db: DbSession, audit: Audit
) -> dict:
    fields = body.model_dump(exclude={"config"})
    fields["config"] = body.config.model_dump(mode="json", by_alias=True)
    device, elder = await device_service.create_device(db, fields, scope)
    await commit_and_audit(db, audit, actor.id, "CREATE_DEVICE", device.id, fields)
    return R.ok(device_service.device_detail(device, elder))


@router.put("/{id}", response_model=Response[DeviceDetail])
async def update_device(
    device_id: DeviceId,
    body: DeviceUpdate,
    actor: DeviceWriter,
    scope: UserScope,
    db: DbSession,
    audit: Audit,
) -> dict:
    device, elder = await device_service.find_device(db, device_id, scope, lock=True)
    fields = body.model_dump(exclude_unset=True, exclude={"config"})
    if "config" in body.model_fields_set:
        patch = body.config.model_dump(mode="json", by_alias=True, exclude_unset=True)
        fields["config"] = {**device.config, **patch}
    changes = {key: value for key, value in fields.items() if value != getattr(device, key)}
    for key, value in changes.items():
        setattr(device, key, value)
    await commit_and_audit(db, audit, actor.id, "UPDATE_DEVICE", device_id, changes)
    return R.ok(device_service.device_detail(device, elder))


@router.post(
    "/{id}/reboot",
    dependencies=[Depends(require_permission("device:write"))],
    response_model=Response[None],
)
async def reboot_device(
    device_id: DeviceId, scope: UserScope, db: DbSession, request: Request
) -> dict:
    device, _ = await device_service.find_device(db, device_id, scope)
    device_no = device.device_no
    await db.rollback()
    if not await request.app.state.mqtt_publisher.publish_cmd(device_no, "restart", {}):
        raise BizException(5001, "设备重启指令下发失败或未获确认")
    return R.ok()
