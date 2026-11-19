from datetime import date, datetime
from typing import Annotated, Generic, TypeVar

from pydantic import AfterValidator, AwareDatetime, BaseModel, ConfigDict, Field, JsonValue
from pydantic.alias_generators import to_camel

from app.schemas.events import Kind, Level, Result, StatsRange, Status
from app.schemas.records import CHINA, EmergencyContacts

T = TypeVar("T")


def as_china(value: datetime) -> datetime:
    return value.astimezone(CHINA)


ChinaDatetime = Annotated[AwareDatetime, AfterValidator(as_china)]
JsonObject = dict[str, JsonValue]


class ResponseFields(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class Response(ResponseFields, Generic[T]):
    code: int
    message: str
    data: T | None
    trace_id: str


class Page(ResponseFields, Generic[T]):
    list: list[T]
    total: int
    page: int
    page_size: int


class ItemList(ResponseFields, Generic[T]):
    list: list[T]


class UserProfile(ResponseFields):
    id: str
    username: str
    nickname: str
    role_code: str
    avatar: str
    community_id: str
    permissions: list[str]
    menus: list[str]


class Tokens(ResponseFields):
    access_token: str
    refresh_token: str
    expires_in: int


class LoginResult(Tokens):
    user: UserProfile


class FamilyBindingItem(ResponseFields):
    binding_id: str
    user_id: str
    name: str
    phone: str | None
    relation: str
    is_primary: bool
    notify_order: int


class DeviceItem(ResponseFields):
    id: str
    device_no: str
    elder_id: str | None
    elder_name: str | None
    type: int
    install_addr: str | None
    algo_version: str | None
    config: JsonObject
    status: int
    last_heartbeat: ChinaDatetime | None
    created_at: ChinaDatetime


class DeviceElder(ResponseFields):
    id: str
    name: str
    community_id: str
    room_no: str | None


class DeviceDetail(DeviceItem):
    elder: DeviceElder | None


class EventSummary(ResponseFields):
    id: str
    event_id: str
    elder_id: str
    elder_name: str
    room_no: str | None
    device_id: str
    device_no: str
    type: Kind
    level: Level
    confidence: float
    occurred_at: ChinaDatetime
    snapshot_url: str | None
    clip_url: str | None
    handled: bool
    handle_result: Result | None


class EventItem(EventSummary):
    handle_remark: str | None
    handled_at: ChinaDatetime | None


class EventDetail(EventItem):
    features: JsonObject
    algo_version: str | None


class EventMedia(ResponseFields):
    snapshot_url: str | None
    clip_url: str | None
    keyframes: list[str]
    expires_in_sec: int


class LevelCounts(ResponseFields):
    p0: int
    p1: int
    p2: int


class EventTypeCounts(ResponseFields):
    fall: int
    long_lie: int


class EventStats(ResponseFields):
    range: StatsRange
    total: int
    today_total: int
    today_p0: int
    unhandled_count: int
    false_positive_count: int
    false_positive_rate: float
    by_level: LevelCounts
    by_type: EventTypeCounts


class ElderItem(ResponseFields):
    id: str
    name: str
    gender: int
    age: int
    birth_date: date
    phone: str | None
    address: str
    room_no: str | None
    community_id: str
    community_name: str
    guardian_id: str | None
    guardian_name: str | None
    health_tags: list[str]
    detect_mode: int
    status: int
    device_online: bool
    alarm_count_30d: int = Field(alias="alarmCount30d")
    created_at: ChinaDatetime


class ElderDetail(ElderItem):
    emergency_contact: EmergencyContacts
    device: DeviceItem | None
    recent_events: list[EventSummary]
    family_bindings: list[FamilyBindingItem]


class ElderState(ResponseFields):
    id: str
    status: int


class AlarmItem(ResponseFields):
    id: str
    level: Level
    status: Status
    elder_id: str
    elder_name: str
    room_no: str | None
    community_name: str
    current_handler: str | None
    escalate_step: int
    created_at: ChinaDatetime
    notified_at: ChinaDatetime | None
    ack_at: ChinaDatetime | None
    resolved_at: ChinaDatetime | None
    response_sec: int | None
    event_type: Kind
    confidence: float
    snapshot_url: str | None
    remaining_sec: int | None


class AlarmElder(ResponseFields):
    id: str
    name: str
    room_no: str | None
    address: str
    age: int
    phone: str | None
    health_tags: list[str]
    primary_contact: JsonObject | None


class AlarmActionItem(ResponseFields):
    id: int
    action: str
    actor: str
    actor_name: str
    channel: str | None
    result: str | None
    detail: JsonObject
    created_at: ChinaDatetime


class TimelineItem(ResponseFields):
    ts: ChinaDatetime
    text: str


class AlarmDetail(AlarmItem):
    elder: AlarmElder
    event: EventDetail
    actions: list[AlarmActionItem]
    timeline: list[TimelineItem]


class PendingCount(ResponseFields):
    count: int


class AlarmStats(ResponseFields):
    range: StatsRange
    total: int
    today_total: int
    avg_response_sec: int
    pending_count: int
    acknowledged_count: int
    escalated_count: int
    dispatched_count: int
    resolved_count: int
    false_positive_count: int


class MockEventResult(ResponseFields):
    event: EventDetail
    alarm: AlarmItem | None


class DashboardOverview(ResponseFields):
    elder_total: int
    elder_online: int
    device_total: int
    device_online: int
    device_offline: int
    alarm_today: int
    alarm_pending: int
    alarm_p0_today: int
    avg_response_sec: int
    false_positive_rate: float
    updated_at: ChinaDatetime


class TrendDay(LevelCounts):
    date: date
    total: int


class CommunityDistribution(ResponseFields):
    community_id: str
    community_name: str
    elder_total: int
    alarm_today: int
    x: float
    y: float


class RealtimeEvent(ResponseFields):
    id: str
    elder_id: str
    elder_name: str
    community_id: str
    community_name: str
    room_no: str | None
    type: Kind
    level: Level
    confidence: float
    occurred_at: ChinaDatetime
    snapshot_url: str | None


class OfflineDevice(ResponseFields):
    id: str
    device_no: str
    elder_id: str | None
    elder_name: str | None
    community_name: str | None
    room_no: str | None
    status: int
    last_heartbeat: ChinaDatetime | None


class DashboardDeviceStatus(ResponseFields):
    total: int
    online: int
    offline: int
    fault: int
    inactive: int
    online_rate: float
    offline_list: list[OfflineDevice]
