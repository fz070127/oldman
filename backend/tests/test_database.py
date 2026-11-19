"""PostgreSQL integration tests. Each test rolls back its own private schema."""

import os
from collections import Counter
from contextlib import aclosing
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import bcrypt
import pytest
from alembic.config import Config
from fastapi import FastAPI, Request
from sqlalchemy import func, inspect, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from alembic import command
from app.db.seed import CHINA, refresh_pending, seed
from app.db.session import get_db
from app.models import Alarm, AlarmAction, Base, Device, Elder, Event, User


async def test_request_sessions_share_lifespan_engine():
    app = FastAPI()
    engine = create_async_engine("postgresql+asyncpg://localhost/unused")
    app.state.db = engine
    request = Request({"type": "http", "app": app})
    try:
        async with aclosing(get_db(request)) as first, aclosing(get_db(request)) as second:
            one = await anext(first)
            factory = app.state.db_sessionmaker
            two = await anext(second)
            assert one is not two
            assert one.bind is two.bind is engine
            assert app.state.db_sessionmaker is factory
    finally:
        await engine.dispose()


@pytest.fixture
async def db():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to run the PostgreSQL integration tests")
    engine = create_async_engine(url)
    schema = f"test_m2_{uuid4().hex}"
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                await connection.execute(text(f"CREATE SCHEMA {schema}"))
                await connection.execute(text(f"SET LOCAL search_path TO {schema}"))
                yield connection
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()


def migration(connection, operation, revision):
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.attributes["connection"] = connection
    operation(config, revision)


@pytest.fixture
async def migrated(db):
    await db.run_sync(migration, command.upgrade, "head")
    return db


async def test_migration_round_trip(migrated):
    def tables(conn):
        return set(
            inspect(conn).get_table_names(schema=conn.scalar(text("select current_schema()")))
        )

    expected = {
        "community",
        "guardian",
        "elder",
        "family_binding",
        "user",
        "role",
        "device",
        "event",
        "alarm",
        "alarm_action",
        "notification",
        "audit_log",
    }
    assert await migrated.run_sync(tables) == expected | {"alembic_version"}
    indexes = dict(
        (
            await migrated.execute(
                text(
                    "SELECT indexname, indexdef FROM pg_indexes WHERE schemaname = current_schema()"
                )
            )
        ).all()
    )
    for name, columns in {
        "ix_event_elder_occurred_at": "(elder_id, occurred_at DESC)",
        "ix_event_device_occurred_at": "(device_id, occurred_at DESC)",
        "ix_alarm_status_created_at": "(status, created_at DESC)",
        "ix_alarm_elder_created_at": "(elder_id, created_at DESC)",
        "ix_device_last_heartbeat": "(last_heartbeat)",
        "ix_alarm_action_alarm_created_at": "(alarm_id, created_at)",
    }.items():
        assert indexes[name].endswith(columns)
    for name in ("uq_event_event_id", "uq_device_device_no", "uq_user_username"):
        assert "UNIQUE INDEX" in indexes[name]
    await migrated.run_sync(migration, command.downgrade, "base")
    assert await migrated.run_sync(tables) == {"alembic_version"}
    assert await migrated.scalar(text("select count(*) from alembic_version")) == 0


async def test_event_id_unique(db):
    # Start with a real 0001 row; 0002 must preserve both the row and its unique constraint.
    migrated = db
    await migrated.run_sync(migration, command.upgrade, "0001")
    await migrated.execute(text("INSERT INTO community(id,name,address) VALUES ('c','C','A')"))
    await migrated.execute(
        text("""
        INSERT INTO elder(id,name,gender,birth_date,community_id,address)
        VALUES ('e','E',1,'1948-01-01','c','A')""")
    )
    await migrated.execute(
        text("INSERT INTO device(id,device_no,elder_id,type) VALUES ('d','N1','e',1)")
    )
    statement = text("""
        INSERT INTO event(id,event_id,device_id,elder_id,type,level,confidence,occurred_at)
        VALUES (:id,'same-edge-id','d','e','FALL','P0',0.9,now())""")
    await migrated.execute(statement, {"id": "first"})
    await migrated.run_sync(migration, command.upgrade, "0002")
    existing = (
        await migrated.execute(
            text("SELECT event_id, handle_remark, handled_at FROM event WHERE id='first'")
        )
    ).one()
    assert existing == ("same-edge-id", None, None)
    columns = (
        await migrated.execute(
            text("""
        SELECT column_name, data_type, character_maximum_length, is_nullable
        FROM information_schema.columns WHERE table_schema=current_schema()
        AND table_name='event' AND column_name IN ('handle_remark','handled_at')
        ORDER BY column_name
    """)
        )
    ).all()
    assert columns == [
        ("handle_remark", "character varying", 512, "YES"),
        ("handled_at", "timestamp with time zone", None, "YES"),
    ]
    with pytest.raises(IntegrityError) as exc:
        async with migrated.begin_nested():
            await migrated.execute(statement, {"id": "second"})
    assert exc.value.orig.sqlstate == "23505" and "uq_event_event_id" in str(exc.value.orig)


async def table_counts(connection):
    return {
        table.name: await connection.scalar(select(func.count()).select_from(table))
        for table in Base.metadata.sorted_tables
    }


async def test_seed_distribution_and_idempotence(migrated):
    factory = async_sessionmaker(migrated, join_transaction_mode="create_savepoint")
    async with factory.begin() as session:
        assert await seed(session) == 500
    counts = await table_counts(migrated)
    assert counts == {
        "community": 5,
        "role": 5,
        "user": 47,
        "guardian": 20,
        "elder": 100,
        "family_binding": 20,
        "device": 90,
        "event": 500,
        "alarm": 500,
        "notification": 500,
        "alarm_action": 1300,
        "audit_log": 0,
    }
    async with factory.begin() as session:
        assert await seed(session) == 0
    assert await table_counts(migrated) == counts

    async with factory() as session:
        users = list(await session.scalars(select(User).where(User.status == 1)))
        assert {u.username for u in users} == (
            {"admin"}
            | {f"guardian{i:02}" for i in range(1, 21)}
            | {f"family{i:02}" for i in range(1, 21)}
            | {f"community{i:02}" for i in range(1, 6)}
        )
        assert bcrypt.checkpw(
            b"123456", next(u.password_hash for u in users if u.username == "admin").encode()
        )
        devices = list(await session.scalars(select(Device)))
        elders = list(await session.scalars(select(Elder)))
        bound = {d.elder_id for d in devices}
        assert sum(e.status == 1 and e.id not in bound for e in elders) == 5
        assert sum(e.status == 2 for e in elders) == 5
        assert sum(d.status == 2 for d in devices) == 5
        assert sum("独居" in e.health_tags for e in elders) == 30

        now = (await session.scalar(select(func.clock_timestamp()))).astimezone(CHINA)
        today = now.date()
        ages = [
            today.year
            - e.birth_date.year
            - ((today.month, today.day) < (e.birth_date.month, e.birth_date.day))
            for e in elders
        ]
        assert min(ages) == 65 and max(ages) == 92
        events = list(await session.scalars(select(Event)))
        assert Counter(e.type for e in events) == {"FALL": 400, "LONG_LIE": 100}
        assert Counter(e.level for e in events) == {"P0": 50, "P1": 150, "P2": 300}
        assert all(now - timedelta(days=30) <= e.occurred_at <= now for e in events)
        assert (
            sum(e.occurred_at.astimezone(CHINA).hour in (6, 7, 8, 18, 19, 20) for e in events) > 250
        )
        assert sum(e.handled for e in events) == 300
        assert sum(e.handled and e.handle_result == "FALSE_POSITIVE" for e in events) == 75

        alarms = list(await session.scalars(select(Alarm)))
        assert Counter(a.status for a in alarms) == {
            "PENDING": 25,
            "ACKNOWLEDGED": 100,
            "ESCALATED": 50,
            "COMMUNITY_DISPATCHED": 25,
            "RESOLVED": 225,
            "FALSE_POSITIVE": 75,
        }
        timeline = {}
        for entry in await session.scalars(
            select(AlarmAction).order_by(AlarmAction.created_at, AlarmAction.id)
        ):
            timeline.setdefault(entry.alarm_id, []).append(entry.action)
        for alarm in alarms:
            if alarm.status == "PENDING":
                assert now - timedelta(minutes=10) <= alarm.created_at <= now
            if alarm.ack_at:
                assert alarm.response_sec == (alarm.ack_at - alarm.notified_at).total_seconds()
                assert 20 <= alarm.response_sec <= 300
            else:
                assert alarm.response_sec is None
            if alarm.status in ("RESOLVED", "FALSE_POSITIVE"):
                assert timeline[alarm.id] == ["NOTIFY", "ACK", "RESOLVE"]

    async with factory.begin() as session:
        other_alarm = await session.scalar(
            select(Alarm.id).where(Alarm.status == "RESOLVED").order_by(Alarm.id).limit(1)
        )
        stale = now - timedelta(minutes=20)
        await session.execute(
            update(Alarm)
            .where((Alarm.status == "PENDING") | (Alarm.id == other_alarm))
            .values(status="PENDING", created_at=stale, notified_at=stale)
        )
        query = select(Alarm.__table__).order_by(Alarm.id)
        before = (await session.execute(query)).mappings().all()
        assert await refresh_pending(session) == 25
        after = (await session.execute(query)).mappings().all()
        refreshed = 0
        now = await session.scalar(select(func.clock_timestamp()))
        for old, new in zip(before, after, strict=True):
            if old["status"] == "PENDING" and old["id"] != other_alarm:
                refreshed += 1
                assert new["created_at"] == new["notified_at"]
                assert timedelta(seconds=1) <= now - new["created_at"] < timedelta(seconds=51)
                assert dict(new) == {
                    **old,
                    "created_at": new["created_at"],
                    "notified_at": new["notified_at"],
                }
            else:
                assert old == new
        assert refreshed == 25
        assert await refresh_pending(session) == 0
        assert (await session.execute(query)).mappings().all() == after
    assert await table_counts(migrated) == counts
