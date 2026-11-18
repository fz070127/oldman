"""Populate the development database. Run with python -m app.db.seed."""

import argparse
import asyncio
import random
import secrets
from datetime import date, datetime, time, timedelta, timezone

import bcrypt
from sqlalchemy import insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.permissions import ROLE_PERMISSIONS
from app.db.session import get_engine
from app.models import (
    Alarm,
    AlarmAction,
    Community,
    Device,
    Elder,
    Event,
    FamilyBinding,
    Guardian,
    Notification,
    Role,
    User,
)
from app.models.enums import (
    Action,
    AlarmStatus,
    Channel,
    DeviceStatus,
    ElderStatus,
    EventLevel,
    EventType,
    HandleResult,
    RoleCode,
)

CHINA = timezone(timedelta(hours=8))
COMMUNITIES = ("幸福里社区", "安康苑", "长乐新村", "夕阳红家园", "康宁小区")
SURNAMES = "王李张刘陈杨黄赵吴周"
GIVEN_NAMES = ("秀兰", "建国", "桂芳", "志强", "玉梅", "国平", "淑芬", "德明", "春华", "永安")
HISTORY_SEED = 42
ROLE_NAMES = {
    RoleCode.ADMIN: "超级管理员",
    RoleCode.COMMUNITY_ADMIN: "社区管理员",
    RoleCode.GUARDIAN: "网格员",
    RoleCode.FAMILY: "家属",
    RoleCode.VIEWER: "只读用户",
}
STATUS_COUNTS = {
    AlarmStatus.PENDING: 25,
    AlarmStatus.ACKNOWLEDGED: 100,
    AlarmStatus.ESCALATED: 50,
    AlarmStatus.COMMUNITY_DISPATCHED: 25,
    AlarmStatus.RESOLVED: 225,
    AlarmStatus.FALSE_POSITIVE: 75,
}


async def insert_missing(session, model, rows):
    """Stable business IDs plus ON CONFLICT also cover concurrent runs."""
    statement = pg_insert(model).values(rows).on_conflict_do_nothing(index_elements=[model.id])
    return set(await session.scalars(statement.returning(model.id)))


def community_id(number):
    return f"C{(number - 1) % 5 + 1:03}"


def guardian_no(number):
    return (number - 1) % 20 + 1


async def seed_directory(session, now):
    await insert_missing(
        session,
        Role,
        [
            {"id": code, "code": code, "name": name, "permissions": list(ROLE_PERMISSIONS[code])}
            for code, name in ROLE_NAMES.items()
        ],
    )
    await insert_missing(
        session,
        Community,
        [
            {
                "id": community_id(i),
                "name": name,
                "address": f"安康路{i}号",
                "contact_name": SURNAMES[i] + "主任",
                "contact_phone": f"1380000{i:04}",
            }
            for i, name in enumerate(COMMUNITIES, 1)
        ],
    )

    accounts = [
        ("admin", "系统管理员", RoleCode.ADMIN, None),
        # Non-login principal permits genuine actor FKs for system-generated actions.
        ("SYSTEM", "系统", RoleCode.VIEWER, None),
    ]
    for prefix, role, count, title in (
        ("community", RoleCode.COMMUNITY_ADMIN, 5, "主任"),
        ("guardian", RoleCode.GUARDIAN, 20, "网格员"),
        ("family", RoleCode.FAMILY, 20, "家属"),
    ):
        accounts.extend(
            (f"{prefix}{i:02}", SURNAMES[(i - 1) % 10] + title, role, community_id(i))
            for i in range(1, count + 1)
        )
    existing = set(
        await session.scalars(select(User.id).where(User.id.in_([a[0] for a in accounts])))
    )
    users = []
    for number, (username, nickname, role, cid) in enumerate(accounts):
        if username in existing:
            continue
        system = username == "SYSTEM"
        password = secrets.token_bytes(32) if system else b"123456"
        password_hash = bcrypt.hashpw(password, bcrypt.gensalt()).decode()
        users.append(
            {
                "id": username,
                "username": username,
                "password_hash": password_hash,
                "nickname": nickname,
                "phone": None if system else f"1390000{number:04}",
                "role_code": role,
                "community_id": cid,
                "status": 0 if system else 1,
            }
        )
    if users:
        await insert_missing(session, User, users)

    await insert_missing(
        session,
        Guardian,
        [
            {
                "id": f"G{i:03}",
                "user_id": f"guardian{i:02}",
                "community_id": community_id(i),
                "name": SURNAMES[(i - 1) % 10] + "网格员",
                "phone": f"1360000{i:04}",
                "elder_count": 5,
            }
            for i in range(1, 21)
        ],
    )
    elders = []
    for i in range(1, 101):
        age = 65 + (i - 1) % 28
        birth = date(now.year - age, (i - 1) % 12 + 1, (i - 1) % 28 + 1)
        if (birth.month, birth.day) > (now.month, now.day):
            birth = birth.replace(year=birth.year - 1)
        tags = ["独居"] if i % 10 < 3 else []
        if i % 4 == 0:
            tags.append("高血压")
        elders.append(
            {
                "id": f"E{i:03}",
                "name": SURNAMES[(i - 1) // 10] + GIVEN_NAMES[(i - 1) % 10],
                "gender": 1 if i % 2 == 0 else 2,
                "birth_date": birth,
                "phone": f"1370000{i:04}",
                "community_id": community_id(i),
                "address": f"{COMMUNITIES[(i - 1) % 5]}{(i - 1) // 10 + 1}栋",
                "room_no": str(301 + i),
                "guardian_id": f"G{guardian_no(i):03}",
                "health_tags": tags,
                "emergency_contact": [
                    {
                        "name": SURNAMES[(i - 1) // 10] + "女士",
                        "phone": f"1350000{i:04}",
                        "relation": "子女",
                        "primary": True,
                    }
                ],
                "detect_mode": 1,
                "status": ElderStatus.PAUSED if i > 95 else ElderStatus.ACTIVE,
            }
        )
    await insert_missing(session, Elder, elders)
    await insert_missing(
        session,
        FamilyBinding,
        [
            {
                "id": f"B{i:03}",
                "user_id": f"family{i:02}",
                "elder_id": f"E{i:03}",
                "relation": "子女",
                "is_primary": True,
                "notify_order": 1,
            }
            for i in range(1, 21)
        ],
    )
    await insert_missing(
        session,
        Device,
        [
            {
                "id": f"D{i:03}",
                "device_no": f"EDGE-{i:04}",
                "elder_id": f"E{i:03}",
                "type": 1,
                "install_addr": elders[i - 1]["address"] + elders[i - 1]["room_no"] + "室",
                "algo_version": "fall-v1.2.0",
                "config": {"roi": [], "furniture": [], "sensitivity": 0.7, "quietHours": []},
                "status": DeviceStatus.OFFLINE if i > 85 else DeviceStatus.ONLINE,
                "last_heartbeat": now - timedelta(seconds=3600 if i > 85 else i % 45),
            }
            for i in range(1, 91)
        ],
    )


def shuffled(rng, counts):
    values = [value for value, count in counts.items() for _ in range(count)]
    rng.shuffle(values)
    return values


def build_history(now):
    rng = random.Random(HISTORY_SEED)
    statuses = shuffled(rng, STATUS_COUNTS)
    types = shuffled(rng, {EventType.FALL: 400, EventType.LONG_LIE: 100})
    levels = shuffled(rng, {EventLevel.P0: 50, EventLevel.P1: 150, EventLevel.P2: 300})
    events, alarms, notifications, actions = [], [], [], []
    for i, (status, kind, level) in enumerate(zip(statuses, types, levels), 1):
        pending = status == AlarmStatus.PENDING
        n = rng.randint(1, 85 if pending else 90)
        elder, handler = f"E{n:03}", f"guardian{guardian_no(n):02}"
        manager = f"community{(n - 1) % 5 + 1:02}"
        notified_user = f"family{n:02}" if n <= 20 else handler
        if pending:
            notified = now - timedelta(seconds=rng.randint(1, 50))
        else:
            day = now.date() - timedelta(days=rng.randint(1, 29))
            hour = rng.choice((6, 7, 8, 18, 19, 20)) if rng.random() < 0.75 else rng.randrange(24)
            notified = datetime.combine(
                day, time(hour, rng.randrange(60), rng.randrange(60)), CHINA
            )
            notified = min(notified, now - timedelta(minutes=16))
        occurred = notified - timedelta(seconds=2)
        closed = status in (AlarmStatus.RESOLVED, AlarmStatus.FALSE_POSITIVE)
        ack = (
            notified + timedelta(seconds=rng.randint(20, 300))
            if closed or status == AlarmStatus.ACKNOWLEDGED
            else None
        )
        resolved = ack + timedelta(seconds=rng.randint(20, 600)) if closed else None
        result = (
            HandleResult.FALSE_POSITIVE
            if status == AlarmStatus.FALSE_POSITIVE
            else HandleResult.TRUE_FALL
        )
        event_id, alarm_id = f"EV{i:04}", f"A{i:04}"
        events.append(
            {
                "id": event_id,
                "event_id": f"demo-edge-{i:04}",
                "device_id": f"D{n:03}",
                "elder_id": elder,
                "type": kind,
                "level": level,
                "confidence": round(rng.uniform(0.64, 0.99), 3),
                "features": {
                    "torsoAngle": round(rng.uniform(5, 24), 1),
                    "heightDrop": round(rng.uniform(0.3, 0.8), 2),
                    "stillDurationSec": rng.randint(60, 240)
                    if kind == EventType.LONG_LIE
                    else rng.randint(3, 24),
                    "trackId": 1,
                    "aspectRatio": round(rng.uniform(1.3, 2.6), 2),
                    "kpConf": round(rng.uniform(0.55, 0.95), 2),
                },
                "algo_version": "fall-v1.2.0",
                "occurred_at": occurred,
                "created_at": notified,
                "handled": closed,
                "handle_result": result if closed else None,
            }
        )
        escalated = status in (AlarmStatus.ESCALATED, AlarmStatus.COMMUNITY_DISPATCHED)
        alarms.append(
            {
                "id": alarm_id,
                "event_id": event_id,
                "elder_id": elder,
                "level": level,
                "status": status,
                "current_handler": manager if closed else (handler if escalated else notified_user),
                "escalate_step": 2
                if status == AlarmStatus.COMMUNITY_DISPATCHED
                else int(escalated),
                "notified_at": notified,
                "ack_at": ack,
                "resolved_at": resolved,
                "response_sec": int((ack - notified).total_seconds()) if ack else None,
                "created_at": notified,
            }
        )
        notifications.append(
            {
                "id": f"N{i:04}",
                "user_id": notified_user,
                "type": "ALARM",
                "title": "疑似跌倒" if kind == EventType.FALL else "长时间倒地",
                "content": f"{elder} 有新的告警，请确认。",
                "biz_id": alarm_id,
                "read": bool(ack),
                "created_at": notified,
            }
        )
        timeline = [(Action.NOTIFY, "SYSTEM", notified, Channel.PUSH, {"to": notified_user})]
        if escalated:
            timeline.append(
                (
                    Action.ESCALATE,
                    "SYSTEM",
                    notified + timedelta(seconds=60),
                    Channel.SMS,
                    {"to": handler},
                )
            )
        if status == AlarmStatus.COMMUNITY_DISPATCHED:
            timeline.append(
                (
                    Action.DISPATCH,
                    manager,
                    notified + timedelta(seconds=120),
                    Channel.INBOX,
                    {"to": handler},
                )
            )
        if ack:
            timeline.append((Action.ACK, notified_user, ack, Channel.INBOX, {}))
        if resolved:
            timeline.append((Action.RESOLVE, manager, resolved, Channel.INBOX, {"result": result}))
        for action, actor, ts, channel, detail in timeline:
            actions.append(
                {
                    "alarm_id": alarm_id,
                    "actor_id": actor,
                    "action": action,
                    "channel": channel,
                    "result": "SENT" if action == Action.NOTIFY else "DELIVERED",
                    "detail": detail,
                    "created_at": ts,
                }
            )
    return events, alarms, notifications, actions


async def seed(session: AsyncSession):
    """Caller owns the transaction. Only newly inserted alarms receive a timeline."""
    now = datetime.now(CHINA).replace(microsecond=0)
    await seed_directory(session, now)
    events, alarms, notifications, actions = build_history(now)
    await insert_missing(session, Event, events)
    new_alarms = await insert_missing(session, Alarm, alarms)
    await insert_missing(session, Notification, notifications)
    new_actions = [action for action in actions if action["alarm_id"] in new_alarms]
    if new_actions:
        await session.execute(insert(AlarmAction), new_actions)
    return len(new_alarms)


async def refresh_pending(session: AsyncSession) -> int:
    """Refresh only seeded alarms that are still pending."""
    statuses = shuffled(random.Random(HISTORY_SEED), STATUS_COUNTS)
    demo_ids = [f"A{i:04}" for i, status in enumerate(statuses, 1) if status == AlarmStatus.PENDING]
    alarms = (
        await session.execute(
            select(Alarm.id, Alarm.created_at, Alarm.notified_at)
            .where(Alarm.id.in_(demo_ids), Alarm.status == AlarmStatus.PENDING)
            .order_by(Alarm.id)
            .with_for_update()
        )
    ).all()
    now = datetime.now(CHINA).replace(microsecond=0)
    oldest, newest = now - timedelta(seconds=50), now - timedelta(seconds=1)
    if all(created == notified and oldest <= created <= newest for _, created, notified in alarms):
        return 0

    values = []
    for offset, (alarm_id, _, _) in enumerate(alarms, 1):
        timestamp = now - timedelta(seconds=offset)
        values.append({"id": alarm_id, "created_at": timestamp, "notified_at": timestamp})
    await session.execute(update(Alarm), values)
    return len(values)


async def main(refresh: bool = False):
    engine = get_engine()
    try:
        async with async_sessionmaker(engine).begin() as session:
            count = await (refresh_pending(session) if refresh else seed(session))
        if refresh:
            print(f"Refresh complete: {count} demo PENDING alarms updated.")
        else:
            print(f"Seed complete: {count} new alarms.")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh-pending", action="store_true", help="刷新演示待确认告警的时间")
    asyncio.run(main(parser.parse_args().refresh_pending))
