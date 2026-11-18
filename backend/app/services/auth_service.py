from datetime import UTC, datetime

import bcrypt
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.exceptions import BizException
from app.core.permissions import ROLE_MENUS, ROLE_PERMISSIONS
from app.core.tokens import AccessClaims, RefreshClaims, TokenIssuer
from app.models import User
from app.services.audit_service import AuditService
from app.services.auth_redis import AuthRedis

DUMMY_PASSWORD_HASH = "$2b$12$taEAQ7ZddoQmjLrHjZamzeFmXtmWUKsq.z/PZUoqF9GHQJXKCeqCu"


def user_profile(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "nickname": user.nickname,
        "roleCode": user.role_code,
        "avatar": user.avatar or "",
        "communityId": user.community_id or "",
        "permissions": list(ROLE_PERMISSIONS.get(user.role_code, ())),
        "menus": list(ROLE_MENUS.get(user.role_code, ())),
    }


async def get_active_user(db: AsyncSession, user_id: str) -> User:
    user = await db.get(User, user_id)
    if user is None or user.status != 1:
        raise BizException(1002, "未登录或登录凭证已失效")
    return user


def _verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


class AuthService:
    def __init__(self, tokens: TokenIssuer, redis: AuthRedis, audit: AuditService) -> None:
        self.tokens = tokens
        self.redis = redis
        self.audit = audit

    async def login(self, db: AsyncSession, username: str, password: str) -> dict:
        check_limit = await self.redis.check_login_limit(username)
        user = await db.scalar(select(User).where(User.username == username, User.status == 1))
        password_hash = user.password_hash if user is not None else DUMMY_PASSWORD_HASH
        valid = await run_in_threadpool(_verify_password, password, password_hash)
        if user is None or not valid:
            if check_limit:
                await self.redis.record_login_failure(username)
            raise BizException(1002, "用户名或密码错误")

        result = {**self.tokens.issue(user.id), "user": user_profile(user)}
        user.last_login_at = datetime.now(UTC)
        await db.commit()
        if check_limit:
            await self.redis.clear_login_failures(username)
        await self.audit.log(user.id, "LOGIN", user.id, {})
        return result

    async def refresh(self, db: AsyncSession, raw_token: str) -> dict:
        token = self.tokens.decode(raw_token, RefreshClaims)
        user = await get_active_user(db, token.sub)
        result = {**self.tokens.issue(user.id), "user": user_profile(user)}
        if not await self.redis.consume_refresh(token):
            raise BizException(1002, "登录凭证已失效")
        return result

    async def logout(self, user: User, token: AccessClaims) -> None:
        await self.redis.revoke_pair(token)
        await self.audit.log(user.id, "LOGOUT", user.id, {})

    async def change_password(
        self, db: AsyncSession, user: User, old_password: str, new_password: str
    ) -> None:
        old_hash = user.password_hash
        if not await run_in_threadpool(_verify_password, old_password, old_hash):
            raise BizException(1001, "原密码错误")
        new_hash = await run_in_threadpool(_hash_password, new_password)
        changed = await db.scalar(
            update(User)
            .where(User.id == user.id, User.status == 1, User.password_hash == old_hash)
            .values(password_hash=new_hash)
            .returning(User.id)
        )
        if changed is None:
            raise BizException(1005, "账号状态或密码已变更，请重试")
        await db.commit()
        await self.audit.log(user.id, "CHANGE_PASSWORD", user.id, {})
