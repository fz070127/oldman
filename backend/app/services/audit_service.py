from asyncio import timeout
from uuid import uuid4

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import AuditLog

logger = structlog.get_logger()


class AuditService:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def log(self, actor_id: str, action: str, target: str, detail: dict) -> None:
        try:
            async with timeout(2), self.sessions.begin() as session:
                session.add(
                    AuditLog(
                        id=uuid4().hex,
                        actor_id=actor_id,
                        action=action,
                        target=target,
                        detail=detail,
                    )
                )
        except Exception as exc:  # noqa: BLE001 - audit failures must leave the request intact.
            logger.warning("audit_write_failed", action=action, error_type=type(exc).__name__)
