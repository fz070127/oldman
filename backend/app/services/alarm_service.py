from datetime import UTC, datetime
from math import ceil

from sqlalchemy import func, select
from sqlalchemy.orm import aliased

from app.core.exceptions import BizException
from app.models import Alarm, AlarmAction, Community, Device, Elder, Event, Guardian, User
from app.models.enums import Action
from app.models.enums import AlarmStatus as S
from app.schemas.events import Ack, Dispatch, Resolve
from app.schemas.records import CHINA
from app.services.escalation_rules import EscalationRules, notified_at
from app.services.event_queries import event_fields, filtered, page_rows, period, scoped
from app.services.records import mask_phone, resolve_directory_id

ALLOWED_TRANSITIONS = {
    S.PENDING: {S.ACKNOWLEDGED, S.ESCALATED},
    S.ACKNOWLEDGED: {S.RESOLVED, S.FALSE_POSITIVE},
    S.ESCALATED: {S.ACKNOWLEDGED, S.COMMUNITY_DISPATCHED},
    S.COMMUNITY_DISPATCHED: {S.RESOLVED, S.FALSE_POSITIVE},
    S.RESOLVED: set(),
    S.FALSE_POSITIVE: set(),
}
TRANSITION_ACTION = {
    S.ACKNOWLEDGED: Action.ACK,
    S.ESCALATED: Action.ESCALATE,
    S.COMMUNITY_DISPATCHED: Action.DISPATCH,
    S.RESOLVED: Action.RESOLVE,
    S.FALSE_POSITIVE: Action.MARK_FALSE,
}
TIMELINE = {
    "DETECT": "检测到{kind}（置信度 {confidence:.0%}）",
    Action.NOTIFY: "已推送{recipient}",
    Action.ESCALATE: "超时未确认，升级至{recipient}",
    Action.ACK: "{role}{actor}已确认",
    Action.DISPATCH: "网格员已派单",
    Action.RESOLVE: "已完结，结果：{result}",
    Action.MARK_FALSE: "已完结，结果：误报",
    Action.DEDUP: "五分钟内重复上报，已合并至本告警",
}
ROLES = {"FAMILY": "家属", "GUARDIAN": "网格员", "ADMIN": "管理员", "COMMUNITY_ADMIN": "社区管理员"}
RESULTS = {"TRUE_FALL": "真实跌倒", "FALSE_POSITIVE": "误报", "UNKNOWN": "待核实"}
KINDS = {"FALL": "跌倒", "LONG_LIE": "久躺"}


def transition(db, alarm, target, actor_id, detail, at):
    if target not in ALLOWED_TRANSITIONS.get(alarm.status, ()):
        raise BizException(1005, "当前状态不允许该操作")
    alarm.status = target
    entry = AlarmAction(
        alarm_id=alarm.id,
        actor_id=actor_id,
        action=TRANSITION_ACTION[target],
        detail=detail,
        created_at=at,
    )
    db.add(entry)
    return entry


def alarm_query(scope):
    return scoped(
        select(Alarm, Elder, Event, Community.name, User.nickname, Device.device_no)
        .join(Elder, Elder.id == Alarm.elder_id)
        .join(Event, Event.id == Alarm.event_id)
        .join(Device, Device.id == Event.device_id)
        .join(Community, Community.id == Elder.community_id)
        .outerjoin(User, User.id == Alarm.current_handler),
        scope,
    )


def alarm_fields(alarm, elder, event, community, handler, device_no, *, rules: EscalationRules):
    remaining = None
    if alarm.status == S.PENDING:
        window = rules.window(alarm.level, alarm.escalate_step + 1)
        if window is not None:
            age = (datetime.now(UTC) - notified_at(alarm)).total_seconds()
            remaining = max(0, ceil(window - max(0, age)))
    return {
        "id": alarm.id,
        "level": alarm.level,
        "status": alarm.status,
        "elderId": elder.id,
        "elderName": elder.name,
        "roomNo": elder.room_no,
        "communityName": community,
        "currentHandler": handler,
        "escalateStep": alarm.escalate_step,
        "createdAt": alarm.created_at,
        "notifiedAt": alarm.notified_at,
        "ackAt": alarm.ack_at,
        "resolvedAt": alarm.resolved_at,
        "responseSec": alarm.response_sec,
        "eventType": event.type,
        "confidence": float(event.confidence),
        "snapshotUrl": event.snapshot_url,
        "remainingSec": remaining,
    }


async def find_alarm(db, alarm_id, scope, *, lock=False):
    statement = alarm_query(scope).where(Alarm.id == alarm_id)
    if lock:
        statement = statement.with_for_update(of=(Alarm, Event))
    row = (await db.execute(statement)).one_or_none()
    if row is None:
        if lock and scope is not None:
            raise BizException(1003, "无权限")
        raise BizException(1004, "告警不存在")
    return row


async def list_alarms(db, query, scope, rules):
    statement = filtered(
        alarm_query(scope), query, Alarm, Alarm.created_at, ("elder_id", "level", "status")
    )
    rows, total = await page_rows(db, statement, query, Alarm.created_at, Alarm.id)
    return [alarm_fields(*row, rules=rules) for row in rows], total


async def pending_count(db, scope):
    return await db.scalar(
        scoped(
            select(func.count()).select_from(Alarm).join(Elder).where(Alarm.status == S.PENDING),
            scope,
        )
    )


async def alarm_stats(db, span, scope):
    start, today, now = period(span)
    fields = {
        S.ACKNOWLEDGED: "acknowledgedCount",
        S.ESCALATED: "escalatedCount",
        S.COMMUNITY_DISPATCHED: "dispatchedCount",
        S.RESOLVED: "resolvedCount",
        S.FALSE_POSITIVE: "falsePositiveCount",
    }
    row = (
        (
            await db.execute(
                scoped(
                    select(
                        func.count().label("total"),
                        func.count().filter(Alarm.created_at >= today).label("todayTotal"),
                        func.coalesce(func.round(func.avg(Alarm.response_sec)), 0).label(
                            "avgResponseSec"
                        ),
                        *(
                            func.count().filter(Alarm.status == status).label(key)
                            for status, key in fields.items()
                        ),
                    )
                    .select_from(Alarm)
                    .join(Elder)
                    .where(Alarm.created_at.between(start, now)),
                    scope,
                )
            )
        )
        .mappings()
        .one()
    )
    return {
        **row,
        "avgResponseSec": int(row["avgResponseSec"]),
        "range": span,
        "pendingCount": await pending_count(db, scope),
    }


def elder_info(elder):
    today = datetime.now(CHINA).date()
    birth = elder.birth_date
    contacts = elder.emergency_contact or []
    primary = next((c for c in contacts if c.get("primary")), contacts[0] if contacts else None)
    return {
        "id": elder.id,
        "name": elder.name,
        "roomNo": elder.room_no,
        "address": elder.address,
        "age": today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day)),
        "phone": mask_phone(elder.phone),
        "healthTags": elder.health_tags,
        "primaryContact": primary,
    }


def build_timeline(event, actions):
    items = [
        {
            "ts": event.occurred_at,
            "text": TIMELINE["DETECT"].format(
                kind=KINDS.get(event.type, event.type), confidence=event.confidence
            ),
        }
    ]
    for action, actor, recipient in actions:
        details = action.detail or {}
        role = ROLES.get(actor.role_code, "")
        fallback = ROLES.get(
            (details.get("target") or "").upper(),
            "网格员" if action.action == Action.ESCALATE else "家属",
        )
        to_role = ROLES.get(recipient.role_code, fallback) if recipient else fallback
        name = details.get("toName") or (recipient.nickname if recipient else None)
        template = TIMELINE.get(action.action, "已记录处置操作")
        if action.action == Action.NOTIFY and action.result == "FAILED":
            template = "{recipient}的通知发送失败"
        text = template.format(
            role=role,
            actor=actor.nickname,
            recipient=f"{to_role}（{name}）" if name else to_role,
            result=RESULTS.get(details.get("result"), "待核实"),
        )
        items.append({"ts": action.created_at, "text": text})
    return sorted(items, key=lambda item: item["ts"])


async def alarm_detail(db, row, scope, rules):
    alarm, elder, event, _, _, device_no = row
    recipient = aliased(User)
    actions = (
        await db.execute(
            scoped(
                select(AlarmAction, User, recipient)
                .join(Alarm, Alarm.id == AlarmAction.alarm_id)
                .join(Elder, Elder.id == Alarm.elder_id)
                .join(User, User.id == AlarmAction.actor_id)
                .outerjoin(recipient, recipient.id == AlarmAction.detail["to"].astext)
                .where(Alarm.id == alarm.id)
                .order_by(AlarmAction.created_at, AlarmAction.id),
                scope,
            )
        )
    ).all()
    return {
        **alarm_fields(*row, rules=rules),
        "elder": elder_info(elder),
        "event": event_fields(event, elder, device_no, full=True),
        "actions": [
            {
                "id": a.id,
                "action": a.action,
                "actor": a.actor_id,
                "actorName": u.nickname,
                "channel": a.channel,
                "result": a.result,
                "detail": a.detail,
                "createdAt": a.created_at,
            }
            for a, u, _ in actions
        ],
        "timeline": build_timeline(event, actions),
    }


async def apply_action(db, row, body: Ack | Dispatch | Resolve, actor):
    alarm, elder, event, *_ = row
    now = datetime.now(UTC)
    detail = body.model_dump(by_alias=True, exclude_none=True)
    handler = actor
    if isinstance(body, Dispatch):
        entry = transition(db, alarm, S.COMMUNITY_DISPATCHED, actor.id, detail, now)
        gid = await resolve_directory_id(db, Guardian, body.guardian_id)
        handler = await db.scalar(
            select(User)
            .join(Guardian, Guardian.user_id == User.id)
            .where(
                Guardian.id == gid, Guardian.community_id == elder.community_id, User.status == 1
            )
        )
        if handler is None:
            raise BizException(1004, "社区网格员不存在")
        entry.detail = {**detail, "to": handler.id, "toName": handler.nickname}
    elif isinstance(body, Resolve):
        false_positive = body.result == "FALSE_POSITIVE"
        target = S.FALSE_POSITIVE if false_positive else S.RESOLVED
        entry = transition(db, alarm, target, actor.id, detail, now)
        alarm.resolved_at = now
        alarm.response_sec = max(
            0,
            int(((alarm.ack_at or now) - (alarm.notified_at or alarm.created_at)).total_seconds()),
        )
        if false_positive:
            event.handled, event.handle_result = True, body.result
            event.handle_remark, event.handled_at = body.note, now
    else:
        entry = transition(db, alarm, S.ACKNOWLEDGED, actor.id, detail, now)
        alarm.ack_at = now
    alarm.current_handler = handler.id
    if body.note is not None:
        alarm.remark = body.note
    return entry.action
