import re
from typing import Any

from fastapi.encoders import jsonable_encoder
from pydantic.alias_generators import to_camel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Community, Device, Guardian
from app.services.audit_service import AuditService

DEMO_SHORT_ID = re.compile(r"[CG][0-9]{2}")


async def resolve_directory_id(
    db: AsyncSession, model: type[Community] | type[Guardian], value: str
) -> str:
    """Accept the contract's short demo IDs while giving actual stored IDs precedence."""
    if DEMO_SHORT_ID.fullmatch(value):
        exact = await db.scalar(select(model.id).where(model.id == value))
        return exact if exact is not None else f"{value[0]}0{value[1:]}"
    return value


def mask_phone(phone: str | None) -> str | None:
    if phone is None:
        return None
    if len(phone) <= 7:
        return "*" * len(phone)
    return f"{phone[:3]}****{phone[-4:]}"


def mask_audit_phones(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: mask_phone(str(item))
            if key.casefold() == "phone" and isinstance(item, (str, int, float))
            else mask_audit_phones(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [mask_audit_phones(item) for item in value]
    return value


async def commit_and_audit(
    db: AsyncSession, audit: AuditService, actor_id: str, action: str, target: str, changes: dict
) -> None:
    await db.commit()
    fields = jsonable_encoder({to_camel(key): value for key, value in changes.items()})
    await audit.log(actor_id, action, target, mask_audit_phones(fields))


def device_fields(device: Device, elder_name: str | None) -> dict:
    return {
        "id": device.id,
        "deviceNo": device.device_no,
        "elderId": device.elder_id,
        "elderName": elder_name,
        "type": device.type,
        "installAddr": device.install_addr,
        "algoVersion": device.algo_version,
        "config": device.config,
        "status": device.status,
        "lastHeartbeat": device.last_heartbeat,
        "createdAt": device.created_at,
    }
