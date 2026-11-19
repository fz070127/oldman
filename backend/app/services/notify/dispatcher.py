import asyncio
from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Alarm, AlarmAction, Elder, FamilyBinding, Guardian, User
from app.models.enums import Action, Channel, RoleCode
from app.services.escalation_rules import EscalationRules, Rule, Target
from app.services.notify.base import Notifier, NotifyResult

log = structlog.get_logger()
RETRY_DELAYS = (2, 5)


async def find_recipient(db: AsyncSession, elder_id: str, target: Target) -> User | None:
    statement = select(User).where(User.status == 1)
    if target == "family_primary":
        statement = (
            statement.join(FamilyBinding, FamilyBinding.user_id == User.id)
            .where(FamilyBinding.elder_id == elder_id, FamilyBinding.is_primary.is_(True))
            .order_by(FamilyBinding.notify_order)
        )
    elif target == "guardian":
        statement = (
            statement.join(Guardian, Guardian.user_id == User.id)
            .join(Elder, Elder.guardian_id == Guardian.id)
            .where(Elder.id == elder_id, Elder.community_id == Guardian.community_id)
        )
    elif target == "community_admin":
        statement = statement.join(Elder, Elder.community_id == User.community_id).where(
            Elder.id == elder_id, User.role_code == RoleCode.COMMUNITY_ADMIN
        )
    else:
        statement = statement.where(User.role_code == RoleCode.ADMIN)
    return await db.scalar(statement.order_by(User.id).limit(1))


async def send_channel(
    notifier: Notifier, recipient: User | None, title: str, content: str, ctx: dict
) -> NotifyResult:
    if recipient is None:
        return NotifyResult(False, notifier.channel, {"reason": "recipient_missing", "attempts": 0})

    to = recipient.id
    if notifier.channel in (Channel.SMS, Channel.CALL):
        to = recipient.phone or ""
    for attempt, delay in enumerate((0, *RETRY_DELAYS), start=1):
        if delay:
            await asyncio.sleep(delay)
        try:
            async with asyncio.timeout(5):
                result = await notifier.send(to, title, content, ctx)
        except Exception as exc:  # noqa: BLE001 - isolate failures from replaceable providers
            result = NotifyResult(False, notifier.channel, {"errorType": type(exc).__name__})
        if result.success:
            break
    return result._replace(detail={**result.detail, "attempts": attempt})


async def notify_new_alarm(
    alarm: Alarm,
    *,
    sessions: async_sessionmaker[AsyncSession],
    rules: EscalationRules,
    notifiers: dict[str, Notifier],
) -> None:
    rule = rules.target(alarm.level, 0)
    try:
        async with sessions() as db:
            recipient = await find_recipient(db, alarm.elder_id, "family_primary")
        await notify_alarm(alarm, 0, rule, recipient, sessions, notifiers)
    except Exception:
        log.exception("alarm_notification_error", alarm_id=alarm.id, step=0)


async def notify_alarm(
    alarm: Alarm,
    step: int,
    rule: Rule,
    recipient: User | None,
    sessions: async_sessionmaker[AsyncSession],
    notifiers: dict[str, Notifier],
) -> None:
    ctx = {"alarm_id": alarm.id, "user_id": recipient.id if recipient else None, "step": step}
    title = "告警升级" if step else "新告警"
    content = f"{alarm.level} 告警，请查看告警详情并确认。"
    results = await asyncio.gather(
        *(
            deliver_channel(notifiers[channel], recipient, title, content, ctx, rule, sessions)
            for channel in rule.channels
        )
    )
    if not any(results):
        log.error("alarm_notify_all_failed", alarm_id=alarm.id, step=step, channels=rule.channels)


async def deliver_channel(
    notifier: Notifier,
    recipient: User | None,
    title: str,
    content: str,
    ctx: dict,
    rule: Rule,
    sessions: async_sessionmaker[AsyncSession],
) -> bool:
    try:
        result = await send_channel(notifier, recipient, title, content, ctx)
        async with sessions.begin() as db:
            db.add(
                AlarmAction(
                    alarm_id=ctx["alarm_id"],
                    actor_id="SYSTEM",
                    action=Action.NOTIFY,
                    channel=result.channel,
                    result="SENT" if result.success else "FAILED",
                    created_at=datetime.now(UTC),
                    detail={
                        **result.detail,
                        "to": ctx["user_id"],
                        "toName": recipient.nickname if recipient else None,
                        "target": rule.to if ctx["step"] else "family_primary",
                        "step": ctx["step"],
                    },
                )
            )
        return result.success
    except Exception:
        log.exception(
            "alarm_notification_error",
            alarm_id=ctx["alarm_id"],
            step=ctx["step"],
            channel=notifier.channel,
        )
        return False
