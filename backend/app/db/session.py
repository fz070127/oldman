from collections.abc import AsyncIterator
from functools import lru_cache

from fastapi import Request
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings


@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    """Process-local engine for commands outside the FastAPI lifespan."""
    return create_async_engine(Settings().database_url, pool_pre_ping=True)


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    """Bind requests to the existing lifespan-owned engine, including in test apps."""
    state = request.app.state
    engine = state.db
    factory = getattr(state, "db_sessionmaker", None)
    if factory is None or factory.kw["bind"] is not engine:
        factory = state.db_sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
