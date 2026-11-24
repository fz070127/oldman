"""系统管理：用户、角色、社区与网格员档案（契约 3.11）。"""

from typing import Annotated
from uuid import uuid4

import bcrypt
from fastapi import APIRouter, Depends, Path, Query
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from app.core.deps import Audit, DbSession, require_permission
from app.core.exceptions import BizException
from app.core.response import R
from app.models import Community, Elder, FamilyBinding, Guardian, Role, User
from app.models.enums import RoleCode
from app.schemas.records import PageFilters, RecordId
from app.schemas.responses import Page, Response
from app.schemas.system import (
    CommunityCreate,
    CommunityItem,
    CommunityUpdate,
    GuardianItem,
    RoleItem,
    SystemFilters,
    SystemUserItem,
    UserCreate,
    UserUpdate,
)
from app.services.records import commit_and_audit, resolve_directory_id

router = APIRouter(prefix="/system", tags=["系统管理"])
Writer = Annotated[User, Depends(require_permission("system:write"))]
Filters = Annotated[SystemFilters, Query()]
DirectoryFilters = Annotated[PageFilters, Query()]
SystemId = Annotated[RecordId, Path(alias="id")]


def _community_item(row: Community) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "address": row.address,
        "contactName": row.contact_name,
        "contactPhone": row.contact_phone,
        "createdAt": row.created_at,
    }


def _user_item(row: User, community_name: str) -> dict:
    return {
        "id": row.id,
        "username": row.username,
        "nickname": row.nickname,
        "phone": row.phone,
        "avatar": row.avatar,
        "roleCode": row.role_code,
        "communityId": row.community_id,
        "communityName": community_name,
        # The non-login SYSTEM principal uses 0 internally; show it as disabled.
        "status": row.status if row.status in (1, 2) else 2,
        "lastLoginAt": row.last_login_at,
        "createdAt": row.created_at,
    }


@router.get("/guardians", dependencies=[Depends(require_permission("system:read"))],
            response_model=Response[Page[GuardianItem]])
async def list_guardians(query: DirectoryFilters, db: DbSession) -> dict:
    statement = (
        select(Guardian, Community.name)
        .join(Community, Community.id == Guardian.community_id)
        .order_by(Guardian.id)
    )
    if query.community_id:
        community_id = await resolve_directory_id(db, Community, query.community_id)
        statement = statement.where(Guardian.community_id == community_id)
    if query.keyword:
        pattern = f"%{query.keyword}%"
        statement = statement.where(
            or_(Guardian.name.ilike(pattern), Guardian.phone.ilike(pattern))
        )
    total = await db.scalar(select(func.count()).select_from(statement.subquery()))
    rows = (await db.execute(statement.offset((query.page - 1) * query.page_size)
                             .limit(query.page_size))).all()
    items = [
        {
            "id": g.id,
            "userId": g.user_id,
            "communityId": g.community_id,
            "communityName": name,
            "name": g.name,
            "phone": g.phone,
            "elderCount": g.elder_count,
        }
        for g, name in rows
    ]
    return R.page(items, total or 0, query.page, query.page_size)


@router.get("/users", dependencies=[Depends(require_permission("system:read"))],
            response_model=Response[Page[SystemUserItem]])
async def list_users(query: Filters, db: DbSession) -> dict:
    statement = select(User, func.coalesce(Community.name, "")).outerjoin(
        Community, Community.id == User.community_id
    )
    if query.keyword:
        pattern = f"%{query.keyword}%"
        statement = statement.where(
            or_(User.username.ilike(pattern), User.nickname.ilike(pattern),
                User.phone.ilike(pattern))
        )
    if query.role_code:
        statement = statement.where(User.role_code == query.role_code)
    if query.community_id:
        community_id = await resolve_directory_id(db, Community, query.community_id)
        statement = statement.where(User.community_id == community_id)
    if query.status is not None:
        # 0 is the non-login SYSTEM principal, treated as disabled in the UI.
        statuses = (0, 2) if query.status == 2 else (1,)
        statement = statement.where(User.status.in_(statuses))
    statement = statement.order_by(User.id)
    total = await db.scalar(select(func.count()).select_from(statement.subquery()))
    rows = (await db.execute(statement.offset((query.page - 1) * query.page_size)
                             .limit(query.page_size))).all()
    items = [_user_item(user, name) for user, name in rows]
    return R.page(items, total or 0, query.page, query.page_size)


@router.get("/roles", dependencies=[Depends(require_permission("system:read"))],
            response_model=Response[dict[str, list[RoleItem]]])
async def list_roles(db: DbSession) -> dict:
    roles = (await db.scalars(select(Role).order_by(Role.id))).all()
    return R.ok({
        "list": [
            {"id": r.id, "code": r.code, "name": r.name, "permissions": r.permissions}
            for r in roles
        ]
    })


@router.get("/communities", dependencies=[Depends(require_permission("system:read"))],
            response_model=Response[Page[CommunityItem]])
async def list_communities(query: DirectoryFilters, db: DbSession) -> dict:
    statement = select(Community)
    if query.keyword:
        pattern = f"%{query.keyword}%"
        statement = statement.where(
            or_(Community.name.ilike(pattern), Community.address.ilike(pattern),
                Community.contact_name.ilike(pattern))
        )
    statement = statement.order_by(Community.id)
    total = await db.scalar(select(func.count()).select_from(statement.subquery()))
    rows = (await db.scalars(statement.offset((query.page - 1) * query.page_size)
                             .limit(query.page_size))).all()
    return R.page([_community_item(row) for row in rows], total or 0,
                  query.page, query.page_size)


@router.post("/communities", status_code=201, response_model=Response[CommunityItem])
async def create_community(body: CommunityCreate, actor: Writer, db: DbSession,
                           audit: Audit) -> dict:
    values = body.model_dump(exclude_none=True)
    community = Community(id=f"C{uuid4().hex[:31]}", **values)
    db.add(community)
    await commit_and_audit(db, audit, actor.id, "CREATE_COMMUNITY", community.id, values)
    return R.ok(_community_item(community))


@router.put("/communities/{id}", response_model=Response[CommunityItem])
async def update_community(record_id: SystemId, body: CommunityUpdate, actor: Writer,
                           db: DbSession, audit: Audit) -> dict:
    community = await db.get(Community, record_id)
    if community is None:
        raise BizException(1004, "社区不存在")
    values = body.model_dump(exclude_unset=True, exclude_none=True)
    for key, value in values.items():
        setattr(community, key, value)
    await commit_and_audit(db, audit, actor.id, "UPDATE_COMMUNITY", record_id, values)
    return R.ok(_community_item(community))


@router.delete("/communities/{id}", response_model=Response[None])
async def delete_community(record_id: SystemId, actor: Writer, db: DbSession,
                           audit: Audit) -> dict:
    community = await db.get(Community, record_id)
    if community is None:
        raise BizException(1004, "社区不存在")
    for model, field, label in (
        (User, User.community_id, "用户"),
        (Guardian, Guardian.community_id, "网格员"),
        (Elder, Elder.community_id, "老人档案"),
    ):
        used = await db.scalar(select(func.count()).select_from(model).where(field == record_id))
        if used:
            raise BizException(1005, f"该社区仍关联 {used} 条{label}记录，请先转移归属")
    await db.delete(community)
    try:
        await commit_and_audit(db, audit, actor.id, "DELETE_COMMUNITY", record_id, {"id": record_id})
    except IntegrityError as error:
        await db.rollback()
        raise BizException(1005, "社区仍有关联记录") from error
    return R.ok(None)


@router.post("/users", status_code=201, response_model=Response[SystemUserItem])
async def create_user(body: UserCreate, actor: Writer, db: DbSession, audit: Audit) -> dict:
    if await db.scalar(select(User.id).where(User.username == body.username)):
        raise BizException(1005, "登录账号已存在")
    if not await db.scalar(select(Role.code).where(Role.code == body.role_code)):
        raise BizException(1001, "角色编码不存在")
    if body.community_id and not await db.scalar(
        select(Community.id).where(Community.id == body.community_id)
    ):
        raise BizException(1001, "所属社区不存在")
    password = body.password.encode()
    if len(password) > 72:
        raise BizException(1001, "初始密码不能超过 72 字节")
    password_hash = await run_in_threadpool(lambda: bcrypt.hashpw(password, bcrypt.gensalt()))
    user = User(
        id=f"U{uuid4().hex[:31]}",
        username=body.username,
        password_hash=password_hash.decode(),
        nickname=body.nickname,
        phone=body.phone,
        role_code=body.role_code,
        community_id=body.community_id,
        status=1,
    )
    db.add(user)
    try:
        await commit_and_audit(db, audit, actor.id, "CREATE_USER", user.id, body.model_dump())
    except IntegrityError as error:
        await db.rollback()
        raise BizException(1005, "登录账号已存在或关联记录已变更") from error
    return R.ok(_user_item(user, await _community_name(db, user.community_id)))


async def _community_name(db: DbSession, community_id: str | None) -> str:
    if not community_id:
        return ""
    return (await db.scalar(select(Community.name).where(Community.id == community_id))) or ""


@router.put("/users/{id}", response_model=Response[SystemUserItem])
async def update_user(record_id: SystemId, body: UserUpdate, actor: Writer, db: DbSession,
                      audit: Audit) -> dict:
    user = await db.get(User, record_id)
    if user is None:
        raise BizException(1004, "用户不存在")
    values = body.model_dump(exclude_unset=True, exclude_none=True)
    if "role_code" in values and not await db.scalar(
        select(Role.code).where(Role.code == values["role_code"])
    ):
        raise BizException(1001, "角色编码不存在")
    if values.get("community_id") and not await db.scalar(
        select(Community.id).where(Community.id == values["community_id"])
    ):
        raise BizException(1001, "所属社区不存在")
    if user.username == "SYSTEM" or (
        user.username == "admin"
        and (values.get("status") == 2 or values.get("role_code", RoleCode.ADMIN) != RoleCode.ADMIN)
    ):
        raise BizException(1005, "内置账号状态和权限受保护")
    for key, value in values.items():
        setattr(user, key, value)
    try:
        await commit_and_audit(db, audit, actor.id, "UPDATE_USER", record_id, values)
    except IntegrityError as error:
        await db.rollback()
        raise BizException(1005, "用户的角色或社区已变更") from error
    return R.ok(_user_item(user, await _community_name(db, user.community_id)))


@router.delete("/users/{id}", response_model=Response[None])
async def delete_user(record_id: SystemId, actor: Writer, db: DbSession, audit: Audit) -> dict:
    user = await db.get(User, record_id)
    if user is None:
        raise BizException(1004, "用户不存在")
    if user.username in ("admin", "SYSTEM") or user.id == actor.id:
        raise BizException(1005, "内置账号不可删除")
    for model, field, label in (
        (Guardian, Guardian.user_id, "网格员档案"),
        (FamilyBinding, FamilyBinding.user_id, "家属绑定"),
    ):
        used = await db.scalar(select(func.count()).select_from(model).where(field == record_id))
        if used:
            raise BizException(1005, f"该用户仍关联 {used} 条{label}，请先解除关联")
    await db.delete(user)
    try:
        await commit_and_audit(db, audit, actor.id, "DELETE_USER", record_id, {"id": record_id})
    except IntegrityError as error:
        await db.rollback()
        raise BizException(1005, "用户仍有关联记录，可停用此账号") from error
    return R.ok(None)
