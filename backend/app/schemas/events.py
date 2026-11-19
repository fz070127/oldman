from datetime import UTC, datetime
from typing import Annotated, Literal, Self
from uuid import uuid4

from pydantic import AwareDatetime, ConfigDict, Field, JsonValue, model_validator
from pydantic.alias_generators import to_camel

from app.schemas.records import NO_NUL, RecordBody, RecordId

Kind = Literal["FALL", "LONG_LIE"]
Level = Literal["P0", "P1", "P2"]
Result = Literal["TRUE_FALL", "FALSE_POSITIVE", "UNKNOWN"]
Status = Literal[
    "PENDING", "ACKNOWLEDGED", "ESCALATED", "COMMUNITY_DISPATCHED", "RESOLVED", "FALSE_POSITIVE"
]
StatsRange = Literal["today", "7d", "30d"]
Note = Annotated[str, Field(max_length=512, pattern=NO_NUL)]
ExternalId = Annotated[str, Field(min_length=1, max_length=64, pattern=NO_NUL)]
Confidence = Annotated[float, Field(ge=0, le=1)]


class Filters(RecordBody):
    page: int = Field(default=1, ge=1, le=2**31 - 1)
    page_size: int = Field(default=20, ge=1, le=100)
    elder_id: RecordId | None = None
    level: Level | None = None
    start_time: AwareDatetime | None = None
    end_time: AwareDatetime | None = None

    @model_validator(mode="after")
    def validate_interval(self) -> Self:
        if self.start_time and self.end_time and self.start_time > self.end_time:
            raise ValueError("开始时间不能晚于结束时间")
        return self


class EventFilters(Filters):
    device_id: RecordId | None = None
    type: Kind | None = None
    handled: bool | None = None


class AlarmFilters(Filters):
    status: Status | None = None


class EventData(RecordBody):
    type: Kind
    level: Level
    confidence: Confidence


class MockEvent(EventData):
    elder_id: RecordId
    event_id: ExternalId = Field(default_factory=lambda: uuid4().hex)


class IngestPayload(EventData):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    event_id: ExternalId
    device_no: ExternalId
    elder_id: RecordId | None = None
    occurred_at: AwareDatetime = Field(default_factory=lambda: datetime.now(UTC))
    features: dict[str, JsonValue] = Field(default_factory=dict)
    algo_version: str | None = Field(default=None, max_length=32, pattern=NO_NUL)
    snapshot_url: Note | None = None
    clip_url: Note | None = None


class Handle(RecordBody):
    result: Result
    remark: Note | None = None


class Ack(RecordBody):
    note: Note | None = None


class Dispatch(Ack):
    guardian_id: RecordId


class Resolve(Ack):
    result: Result
    need_follow_up: bool
