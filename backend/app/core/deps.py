from collections.abc import Callable, Coroutine
from typing import Annotated, Any

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import false, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import ColumnElement

from app.core.exceptions import BizException
from app.core.permissions import has_permission
from app.core.tokens import AccessClaims, TokenIssuer
from app.db.session import get_db, get_sessionmaker
from app.models import Elder, FamilyBinding, Guardian, User
from app.models.enums import RoleCode
from app.services.audit_service import AuditService
from app.services.auth_redis import AuthRedis
from app.services.auth_service import AuthService, get_active_user

bearer = HTTPBearer(auto_error=False)
DbSession = Annotated[AsyncSession, Depends(get_db)]


def get_audit_service(request: Request) -> AuditService:
    return AuditService(get_sessionmaker(request))


Audit = Annotated[AuditService, Depends(get_audit_service)]


async def get_auth_service(request: Request) -> AuthService:
    return AuthService(
        TokenIssuer(request.app.state.settings),
        AuthRedis(request.app.state.redis),
        get_audit_service(request),
    )


Auth = Annotated[AuthService, Depends(get_auth_service)]


async def get_access_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)], auth: Auth
) -> AccessClaims:
    if credentials is None:
        raise BizException(1002, "未登录")
    token = auth.tokens.decode(credentials.credentials, AccessClaims)
    if await auth.redis.is_revoked(token):
        raise BizException(1002, "登录凭证已失效")
    return token


AccessToken = Annotated[AccessClaims, Depends(get_access_token)]


async def get_current_user(token: AccessToken, db: DbSession) -> User:
    return await get_active_user(db, token.sub)


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_permission(permission: str) -> Callable[[User], Coroutine[Any, Any, User]]:
    async def check(user: CurrentUser) -> User:
        if not has_permission(user.role_code, permission):
            raise BizException(1003, "无权限")
        return user

    return check


async def get_user_scope(user: CurrentUser) -> ColumnElement[bool] | None:
    """Apply the predicate to queries over Elder, joining Elder for related records."""
    if user.role_code == RoleCode.ADMIN:
        return None
    if user.role_code in (RoleCode.COMMUNITY_ADMIN, RoleCode.VIEWER) and user.community_id:
        return Elder.community_id == user.community_id
    if user.role_code == RoleCode.GUARDIAN:
        guardian_id = select(Guardian.id).where(Guardian.user_id == user.id).scalar_subquery()
        return Elder.guardian_id == guardian_id
    if user.role_code == RoleCode.FAMILY:
        elder_ids = select(FamilyBinding.elder_id).where(FamilyBinding.user_id == user.id)
        return Elder.id.in_(elder_ids)
    return false()


UserScope = Annotated[ColumnElement[bool] | None, Depends(get_user_scope)]
