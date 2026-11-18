from datetime import date, datetime, timedelta, timezone
from typing import Annotated, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StringConstraints,
    model_validator,
)
from pydantic.alias_generators import to_camel

CHINA = timezone(timedelta(hours=8))

NO_NUL = r"^[^\x00]*$"
RecordId = Annotated[str, StringConstraints(min_length=1, max_length=32, pattern=NO_NUL)]
Name = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=32, pattern=NO_NUL)
]
Phone = Annotated[str, StringConstraints(pattern=r"^1[0-9]{10}$")]
Address = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255, pattern=NO_NUL)
]
RoomNo = Annotated[str, StringConstraints(max_length=32, pattern=NO_NUL)]
Gender = Annotated[int, Field(strict=True, ge=1, le=2)]
ElderStatus = Annotated[int, Field(strict=True, ge=1, le=3)]
DetectMode = Annotated[int, Field(strict=True, ge=1, le=3)]
EmergencyContacts = list[dict[str, JsonValue]]


def check_birth_date(value: date) -> date:
    if value > datetime.now(CHINA).date():
        raise ValueError("出生日期不能晚于今天")
    return value


BirthDate = Annotated[date, AfterValidator(check_birth_date)]


class PageFilters(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    page: int = Field(default=1, ge=1, le=2**31 - 1)
    page_size: int = Field(default=20, ge=1, le=100)
    keyword: str = Field(default="", max_length=255, pattern=NO_NUL)
    community_id: RecordId | None = None


class ElderFilters(PageFilters):
    status: int | None = Field(default=None, ge=1, le=3)
    guardian_id: RecordId | None = None


class DeviceFilters(PageFilters):
    status: int | None = Field(default=None, ge=0, le=3)


class RecordBody(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, extra="forbid", allow_inf_nan=False)


class ElderCreate(RecordBody):
    name: Name
    gender: Gender
    birth_date: BirthDate
    phone: Phone
    community_id: RecordId
    address: Address
    room_no: RoomNo | None = None
    guardian_id: RecordId
    health_tags: list[str] = Field(default_factory=list)
    emergency_contact: EmergencyContacts = Field(default_factory=list)
    detect_mode: DetectMode = 1


class ElderUpdate(RecordBody):
    name: Name | None = None
    gender: Gender | None = None
    birth_date: BirthDate | None = None
    phone: Phone | None = None
    address: Address | None = None
    room_no: RoomNo | None = None
    health_tags: list[str] | None = None
    emergency_contact: EmergencyContacts | None = None
    detect_mode: DetectMode | None = None
    status: ElderStatus | None = None

    @model_validator(mode="after")
    def check_required_values(self) -> Self:
        for field in self.model_fields_set - {"phone", "room_no"}:
            if getattr(self, field) is None:
                raise ValueError(f"{to_camel(field)} 不能为空")
        return self


class FamilyBindingCreate(RecordBody):
    user_id: RecordId
    relation: Name
    is_primary: bool = False
    notify_order: int = Field(default=1, strict=True, ge=1, le=32767)


Coordinate = Annotated[float, Field(strict=True, ge=0, le=1)]
Point = tuple[Coordinate, Coordinate]


class FurnitureZone(BaseModel):
    model_config = ConfigDict(extra="allow", allow_inf_nan=False)

    type: Name
    points: list[Point]


class DeviceConfig(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, extra="allow", allow_inf_nan=False)

    roi: list[Point] = Field(default_factory=list)
    furniture: list[FurnitureZone] = Field(default_factory=list)
    sensitivity: Coordinate = 0.7
    quiet_hours: list[str] = Field(default_factory=list)


class DeviceCreate(RecordBody):
    device_no: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64, pattern=NO_NUL)
    ]
    elder_id: RecordId
    type: Annotated[int, Field(strict=True, ge=1, le=3)]
    install_addr: Address | None = None
    config: DeviceConfig = Field(default_factory=DeviceConfig)


class DeviceUpdate(RecordBody):
    install_addr: Address | None = None
    config: DeviceConfig = Field(default_factory=DeviceConfig)
