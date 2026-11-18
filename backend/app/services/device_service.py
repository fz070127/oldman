from uuid import uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import ColumnElement

from app.core.exceptions import BizException
from app.models import Community, Device, Elder
from app.schemas.records import DeviceFilters
from app.services.elder_service import find_elder
from app.services.records import device_fields, resolve_directory_id


async def list_devices(
    db: AsyncSession, query: DeviceFilters, scope: ColumnElement[bool] | None
) -> tuple[list[dict], int]:
    filters = []
    if scope is not None:
        filters.append(scope)
    if query.status is not None:
        filters.append(Device.status == query.status)
    if query.keyword:
        filters.append(
            or_(
                Device.device_no.icontains(query.keyword, autoescape=True),
                Device.install_addr.icontains(query.keyword, autoescape=True),
            )
        )
    if query.community_id:
        filters.append(
            Elder.community_id == await resolve_directory_id(db, Community, query.community_id)
        )

    # The outer join keeps unbound devices visible to ADMIN. Elder predicates narrow other scopes.
    joined = Device.__table__.outerjoin(Elder.__table__, Device.elder_id == Elder.id)
    total = await db.scalar(select(func.count()).select_from(joined).where(*filters))
    rows = await db.execute(
        select(Device, Elder.name)
        .select_from(joined)
        .where(*filters)
        .order_by(Device.created_at.desc(), Device.id)
        .offset((query.page - 1) * query.page_size)
        .limit(query.page_size)
    )
    return [device_fields(device, elder_name) for device, elder_name in rows], total or 0


async def find_device(
    db: AsyncSession, device_id: str, scope: ColumnElement[bool] | None, *, lock: bool = False
) -> tuple[Device, Elder | None]:
    statement = select(Device, Elder).outerjoin(Elder, Device.elder_id == Elder.id)
    statement = statement.where(Device.id == device_id)
    if scope is not None:
        statement = statement.where(scope)
    if lock:
        statement = statement.with_for_update(of=Device)
    row = (await db.execute(statement)).one_or_none()
    if row is None:
        raise BizException(1004, "设备不存在")
    return row[0], row[1]


def device_detail(device: Device, elder: Elder | None) -> dict:
    return {
        **device_fields(device, elder.name if elder else None),
        "elder": {
            "id": elder.id,
            "name": elder.name,
            "communityId": elder.community_id,
            "roomNo": elder.room_no,
        }
        if elder
        else None,
    }


async def create_device(
    db: AsyncSession, fields: dict, scope: ColumnElement[bool] | None
) -> tuple[Device, Elder]:
    # M2 has no unique constraint on elder_id. Lock the elder before checking its devices.
    elder = await find_elder(db, fields["elder_id"], scope, lock=True)
    if await db.scalar(select(Device.id).where(Device.elder_id == elder.id).limit(1)) is not None:
        raise BizException(1005, "该老人已绑定设备")
    statement = (
        insert(Device)
        .values(id=uuid4().hex, **fields)
        .on_conflict_do_nothing(index_elements=[Device.device_no])
        .returning(Device)
    )
    device = await db.scalar(statement)
    if device is None:
        raise BizException(1005, "设备号已存在")
    return device, elder
