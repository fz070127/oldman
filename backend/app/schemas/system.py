"""系统管理请求与响应模型（契约 3.11）。"""

from datetime import datetime
from typing import Annotated

from pydantic import Field, StringConstraints

from app.schemas.records import Address, Name, PageFilters, Phone, RecordBody, RecordId
from app.schemas.responses import ChinaDatetime, ResponseFields


class SystemFilters(PageFilters):
    role_code: RecordId | None = None
    status: int | None = Field(default=None, ge=1, le=2)


class CommunityCreate(RecordBody):
    name: Name
    address: Address
    contact_name: Name | None = None
    contact_phone: Phone | None = None


class CommunityUpdate(RecordBody):
    name: Name | None = None
    address: Address | None = None
    contact_name: Name | None = None
    contact_phone: Phone | None = None


class UserCreate(RecordBody):
    username: Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_]{3,24}$")]
    nickname: Name
    phone: Phone | None = None
    role_code: RecordId
    community_id: RecordId | None = None
    password: str = Field(min_length=8, max_length=72, exclude=True)


class UserUpdate(RecordBody):
    nickname: Name | None = None
    phone: Phone | None = None
    role_code: RecordId | None = None
    community_id: RecordId | None = None
    status: int | None = Field(default=None, ge=1, le=2)


class CommunityItem(ResponseFields):
    id: str
    name: str
    address: str
    contact_name: str | None
    contact_phone: str | None
    created_at: ChinaDatetime


class GuardianItem(ResponseFields):
    id: str
    user_id: str
    community_id: str
    community_name: str
    name: str
    phone: str
    elder_count: int


class SystemUserItem(ResponseFields):
    id: str
    username: str
    nickname: str
    phone: str | None
    avatar: str | None
    role_code: str
    community_id: str | None
    community_name: str
    status: int
    last_login_at: datetime | None
    created_at: ChinaDatetime


class RoleItem(ResponseFields):
    id: str
    code: str
    name: str
    permissions: list[str]
