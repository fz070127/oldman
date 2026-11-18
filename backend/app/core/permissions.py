from app.models.enums import RoleCode

ROLE_PERMISSIONS = {
    RoleCode.ADMIN: ("*",),
    RoleCode.COMMUNITY_ADMIN: (
        "elder:read",
        "elder:write",
        "device:*",
        "event:*",
        "alarm:*",
        "dashboard:*",
    ),
    RoleCode.GUARDIAN: ("elder:read", "event:read", "alarm:read", "alarm:ack", "alarm:dispatch"),
    RoleCode.FAMILY: ("family:read", "alarm:ack"),
    RoleCode.VIEWER: ("dashboard:read",),
}

ROLE_MENUS = {
    RoleCode.ADMIN: ("dashboard", "elder", "device", "event", "alarm", "screen", "system"),
    RoleCode.COMMUNITY_ADMIN: ("dashboard", "elder", "device", "event", "alarm", "screen"),
    RoleCode.GUARDIAN: ("dashboard", "elder", "alarm", "event"),
    RoleCode.FAMILY: ("family",),
    RoleCode.VIEWER: ("dashboard", "screen"),
}


def has_permission(role_code: str, permission: str) -> bool:
    allowed = ROLE_PERMISSIONS.get(role_code, ())
    resource, separator, _ = permission.partition(":")
    return (
        "*" in allowed or permission in allowed or (bool(separator) and f"{resource}:*" in allowed)
    )
