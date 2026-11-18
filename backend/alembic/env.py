import asyncio

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context
from app.core.config import Settings
from app.models import Base


def migrate(connection):
    context.configure(
        connection=connection, target_metadata=Base.metadata, compare_server_default=True
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_online():
    engine = create_async_engine(Settings().database_url, poolclass=pool.NullPool)
    try:
        async with engine.connect() as connection:
            await connection.run_sync(migrate)
    finally:
        await engine.dispose()


if context.is_offline_mode():
    context.configure(
        url=Settings().database_url, target_metadata=Base.metadata, literal_binds=True
    )
    with context.begin_transaction():
        context.run_migrations()
elif "connection" in context.config.attributes:
    migrate(context.config.attributes["connection"])
else:
    asyncio.run(run_online())
