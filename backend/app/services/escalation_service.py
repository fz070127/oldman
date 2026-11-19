import asyncio
from collections.abc import Coroutine
from datetime import UTC, datetime
from time import monotonic, time

import structlog
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.models import Alarm, AlarmAction, Elder, Event
from app.models.enums import Action, Channel
from app.models.enums import AlarmStatus as S
from app.services import alarm_service
from app.services.escalation_rules import EscalationRules
from app.services.notify import dispatcher
from app.services.notify.registry import build_registry
from app.ws.publisher import RealtimePublisher, alarm_update

log = structlog.get_logger()
QUEUE_KEY = "alarm:escalate"
BATCH_SIZE = 100
QUEUE_ERRORS = (RedisError, OSError)


class EscalationQueue:
    def __init__(self, redis: Redis):
        self.redis = redis
        self.memory: asyncio.PriorityQueue[tuple[float, str]] = asyncio.PriorityQueue()
        self.degraded = False
        self.connected_once = False
        self.retry_at = 0.0

    def warn_degraded(self, error: Exception) -> None:
        self.retry_at = monotonic() + 5
        if not self.degraded:
            log.warning(
                "alarm_escalation_redis_degraded",
                error_type=type(error).__name__,
                message="Using process-local memory queue. Pending memory jobs are lost on restart.",
            )
            self.degraded = True

    async def enqueue(self, member: str, due_ts: float) -> None:
        if self.degraded:
            self.memory.put_nowait((due_ts, member))
            return
        try:
            async with asyncio.timeout(1):
                await self.redis.zadd(QUEUE_KEY, {member: due_ts})
                self.connected_once = True
        except QUEUE_ERRORS as exc:
            self.warn_degraded(exc)
            self.memory.put_nowait((due_ts, member))

    def take_memory(self, until: float) -> list[tuple[float, str]]:
        items = []
        while not self.memory.empty() and len(items) < BATCH_SIZE:
            item = self.memory.get_nowait()
            self.memory.task_done()
            if item[0] > until:
                self.memory.put_nowait(item)
                break
            items.append(item)
        return items

    async def ready(self) -> list[tuple[str, float | None]]:
        now = time()
        if self.degraded and monotonic() < self.retry_at:
            return [(member, due) for due, member in self.take_memory(now)]
        try:
            async with asyncio.timeout(1):
                members = await self.redis.zrangebyscore(
                    QUEUE_KEY, "-inf", now, start=0, num=BATCH_SIZE
                )
                self.connected_once = True
                if self.degraded:
                    pending = self.take_memory(float("inf"))
                    if pending:
                        try:
                            await self.redis.zadd(
                                QUEUE_KEY, {member: due for due, member in pending}
                            )
                        except BaseException:
                            for item in pending:
                                self.memory.put_nowait(item)
                            raise
                    if self.memory.empty():
                        self.degraded = False
                        log.info("alarm_escalation_redis_recovered")
        except QUEUE_ERRORS as exc:
            self.warn_degraded(exc)
            return [(member, due) for due, member in self.take_memory(now)]

        return [(item.decode() if isinstance(item, bytes) else item, None) for item in members]

    async def remove(self, member: str) -> None:
        try:
            async with asyncio.timeout(1):
                await self.redis.zrem(QUEUE_KEY, member)
        except QUEUE_ERRORS as exc:
            self.warn_degraded(exc)


class EscalationEngine:
    def __init__(
        self,
        settings: Settings,
        sessions: async_sessionmaker[AsyncSession],
        redis: Redis,
        *,
        realtime: RealtimePublisher | None = None,
    ):
        self.sessions = sessions
        self.rules = EscalationRules(settings)
        self.queue = EscalationQueue(redis)
        self.realtime = realtime
        self.notifiers = build_registry(
            settings.notify_provider, sessions, realtime.connections if realtime else None
        )
        self.interval = settings.escalate_poll_interval_sec
        self.deliveries: set[asyncio.Task] = set()
        self.reconciled_state: tuple[int, bool] | None = None

    async def new_alarm(
        self, alarm: Alarm, event: Event | None = None, elder: Elder | None = None
    ) -> None:
        message = None
        if self.realtime is not None and event is not None and elder is not None:
            rule = self.rules.target(alarm.level, 0)
            message = await self.realtime.new_alarm(
                alarm,
                event,
                elder,
                self.rules,
                exclude_user_id=alarm.current_handler if Channel.WS in rule.channels else None,
            )
        await self.schedule(alarm, 1)
        await dispatcher.notify_new_alarm(
            alarm,
            sessions=self.sessions,
            rules=self.rules,
            notifiers=self.notifiers,
            ws_message=message,
        )

    async def schedule(self, alarm: Alarm, step: int) -> None:
        due = self.rules.due(alarm, step)
        if due is not None:
            await self.queue.enqueue(f"{alarm.id}:{step}", due)

    async def process(self, alarm_id: str, step: int, *, from_memory: bool = False) -> bool:
        """Return whether the queue member can be removed."""
        async with self.sessions.begin() as db:
            alarm = await db.scalar(select(Alarm).where(Alarm.id == alarm_id).with_for_update())
            if alarm is None or not self.can_escalate(alarm):
                log.info(
                    "alarm_escalation_skipped",
                    alarm_id=alarm_id,
                    step=step,
                    status=alarm.status if alarm else "MISSING",
                )
                return True
            current = alarm.escalate_step
            if step > current + 1:
                return False
            if step <= current:
                log.info(
                    "alarm_escalation_skipped",
                    alarm_id=alarm_id,
                    step=step,
                    reason="already_applied",
                )
                # Recover if a worker committed this step and exited before scheduling the next.
                if step == current:
                    await self.schedule(alarm, current + 1)
                return True

            due = self.rules.due(alarm, step)
            if due is None:
                return True
            now = datetime.now(UTC)
            if now.timestamp() < due:
                await self.schedule(alarm, step)
                return from_memory

            rule = self.rules.target(alarm.level, step)
            recipient = await dispatcher.find_recipient(db, alarm.elder_id, rule.to)
            previous_handler = alarm.current_handler
            alarm.escalate_step = step
            alarm.current_handler = recipient.id if recipient else None
            detail = {
                "from": previous_handler,
                "to": alarm.current_handler,
                "toName": recipient.nickname if recipient else None,
                "target": rule.to,
                "step": step,
            }
            if alarm.status == S.PENDING:
                alarm_service.transition(db, alarm, S.ESCALATED, "SYSTEM", detail, now)
            else:
                db.add(
                    AlarmAction(
                        alarm_id=alarm.id,
                        actor_id="SYSTEM",
                        action=Action.ESCALATE,
                        detail=detail,
                        created_at=now,
                    )
                )

        log.info(
            "alarm_escalated",
            alarm_id=alarm.id,
            step=step,
            status=alarm.status,
            target=rule.to,
            late_sec=round(now.timestamp() - due, 3),
        )
        if self.realtime is not None:
            await self.realtime.alarm(
                alarm.elder_id,
                alarm_update(alarm, recipient.nickname if recipient else None),
                exclude_user_id=alarm.current_handler if Channel.WS in rule.channels else None,
            )
        self.start_delivery(
            dispatcher.notify_alarm(alarm, step, rule, recipient, self.sessions, self.notifiers)
        )
        await self.schedule(alarm, step + 1)
        return True

    @staticmethod
    def can_escalate(alarm: Alarm) -> bool:
        # After the first automatic transition, unacknowledged ESCALATED alarms stay eligible.
        return alarm.ack_at is None and alarm.status in (S.PENDING, S.ESCALATED)

    def start_delivery(self, delivery: Coroutine) -> None:
        task = asyncio.create_task(delivery)
        self.deliveries.add(task)
        task.add_done_callback(self.deliveries.discard)

    async def reconcile(self) -> None:
        state = (self.rules.revision, self.queue.degraded)
        if not self.queue.connected_once or self.reconciled_state == state:
            return
        # Recover committed jobs on startup, rule changes and transitions between queue backends.
        async with self.sessions() as db:
            alarms = await db.stream_scalars(
                select(Alarm)
                .where(
                    Alarm.status.in_((S.PENDING, S.ESCALATED)),
                    Alarm.ack_at.is_(None),
                    Alarm.notified_at.is_not(None),
                )
                .execution_options(yield_per=100)
            )
            async for alarm in alarms:
                await self.schedule(alarm, alarm.escalate_step + 1)
        self.reconciled_state = state

    async def scan(self) -> None:
        for member, memory_due in await self.queue.ready():
            try:
                alarm_id, separator, number = member.rpartition(":")
                if not separator or not alarm_id or not number.isdecimal() or int(number) < 1:
                    log.warning("alarm_escalation_invalid_member", member=member)
                    remove = True
                else:
                    remove = await self.process(
                        alarm_id, int(number), from_memory=memory_due is not None
                    )
                if remove and memory_due is None:
                    await self.queue.remove(member)
                if not remove and memory_due is not None:
                    # Preserve jobs which cannot advance yet, including a Redis outage mid-scan.
                    self.queue.memory.put_nowait((memory_due, member))
            except Exception:
                if memory_due is not None:
                    self.queue.memory.put_nowait((memory_due, member))
                log.exception("alarm_escalation_job_failed", member=member)
        await self.reconcile()

    async def run(self) -> None:
        try:
            while True:
                try:
                    await self.scan()
                except Exception:
                    log.exception("alarm_escalation_scan_failed")
                await asyncio.sleep(self.interval)
        finally:
            await asyncio.gather(*tuple(self.deliveries), return_exceptions=True)
