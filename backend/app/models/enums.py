class RoleCode:
    ADMIN = "ADMIN"
    COMMUNITY_ADMIN = "COMMUNITY_ADMIN"
    GUARDIAN = "GUARDIAN"
    FAMILY = "FAMILY"
    VIEWER = "VIEWER"


class ElderStatus:
    ACTIVE = 1
    PAUSED = 2
    DECEASED = 3


class DeviceStatus:
    INACTIVE = 0
    ONLINE = 1
    OFFLINE = 2
    FAULT = 3


class EventType:
    FALL = "FALL"
    LONG_LIE = "LONG_LIE"


class EventLevel:
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"


class HandleResult:
    TRUE_FALL = "TRUE_FALL"
    FALSE_POSITIVE = "FALSE_POSITIVE"
    UNKNOWN = "UNKNOWN"


class AlarmStatus:
    PENDING = "PENDING"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    ESCALATED = "ESCALATED"
    COMMUNITY_DISPATCHED = "COMMUNITY_DISPATCHED"
    RESOLVED = "RESOLVED"
    FALSE_POSITIVE = "FALSE_POSITIVE"


class Action:
    NOTIFY = "NOTIFY"
    ACK = "ACK"
    ESCALATE = "ESCALATE"
    DISPATCH = "DISPATCH"
    RESOLVE = "RESOLVE"
    MARK_FALSE = "MARK_FALSE"
    DEDUP = "DEDUP"


class Channel:
    PUSH = "PUSH"
    SMS = "SMS"
    CALL = "CALL"
    WS = "WS"
    INBOX = "INBOX"
