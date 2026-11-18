from asyncio import timeout

import structlog
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.exceptions import BizException
from app.core.tokens import AccessClaims, TokenClaims

logger = structlog.get_logger()
FAIL_LIMIT = 5
LOCK_SECONDS = 600
LOCK_MESSAGE = "登录失败次数过多，请在 10 分钟后重试"

# Start the full lock period at the fifth failure. Attempts during the lock do not extend it.
RECORD_FAILURE = """
local failures = tonumber(redis.call('GET', KEYS[1]) or '0')
local limit = tonumber(ARGV[1])
if failures >= limit then return limit + 1 end
failures = redis.call('INCR', KEYS[1])
if failures == 1 or failures == limit then
    redis.call('EXPIRE', KEYS[1], ARGV[2])
end
return failures
"""


class AuthRedis:
    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    async def _call(self, operation, *args, **kwargs):
        try:
            async with timeout(1):
                return await operation(*args, **kwargs)
        except (RedisError, OSError) as exc:
            logger.warning(
                "auth_redis_degraded", operation=operation.__name__, error_type=type(exc).__name__
            )
            return None

    async def check_login_limit(self, username: str) -> bool:
        async def read_login_failures() -> int:
            return int(await self.redis.get(f"login:fail:{username}") or 0)

        failures = await self._call(read_login_failures)
        if failures is None:
            return False
        if failures >= FAIL_LIMIT:
            raise BizException(1006, LOCK_MESSAGE)
        return True

    async def record_login_failure(self, username: str) -> None:
        failures = await self._call(
            self.redis.eval, RECORD_FAILURE, 1, f"login:fail:{username}", FAIL_LIMIT, LOCK_SECONDS
        )
        if (failures or 0) > FAIL_LIMIT:
            raise BizException(1006, LOCK_MESSAGE)

    async def clear_login_failures(self, username: str) -> None:
        await self._call(self.redis.delete, f"login:fail:{username}")

    @staticmethod
    def _blacklist(jti: str) -> str:
        return f"auth:blacklist:{jti}"

    async def is_revoked(self, token: TokenClaims) -> bool:
        return bool(await self._call(self.redis.exists, self._blacklist(token.jti)))

    async def consume_refresh(self, token: TokenClaims) -> bool:
        # Redis returns None for an unmet NX condition, so wrap that result as False.
        async def set_if_unused() -> bool:
            return bool(
                await self.redis.set(self._blacklist(token.jti), "1", exat=token.exp, nx=True)
            )

        return await self._call(set_if_unused) is not False

    async def revoke_pair(self, token: AccessClaims) -> None:
        async def revoke_tokens() -> None:
            async with self.redis.pipeline() as pipe:
                pipe.set(self._blacklist(token.jti), "1", exat=token.exp)
                pipe.set(self._blacklist(token.refresh_jti), "1", exat=token.refresh_exp)
                await pipe.execute()

        await self._call(revoke_tokens)
