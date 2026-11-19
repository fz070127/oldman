import asyncio
import sys
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Literal

import uvicorn
from asyncpg import PostgresError
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from app.api.v1.events import mock_router
from app.api.v1.router import router
from app.core.config import Settings
from app.core.exceptions import register_handlers
from app.core.logging import TraceMiddleware, configure_logging
from app.core.response import R
from app.mqtt.client import MqttClient
from app.mqtt.handlers import MqttHandlers
from app.mqtt.publisher import MqttPublisher

DependencyStatus = Literal["up", "down"]


class HealthData(BaseModel):
    status: Literal["up"]
    db: DependencyStatus
    redis: DependencyStatus
    mqtt: DependencyStatus


class HealthResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel)

    code: Literal[0]
    message: str
    data: HealthData
    trace_id: str


async def check_database(engine: AsyncEngine) -> DependencyStatus:
    try:
        async with asyncio.timeout(2), engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return "up"
    except (OSError, SQLAlchemyError, PostgresError):
        return "down"


async def check_redis(client: Redis) -> DependencyStatus:
    try:
        async with asyncio.timeout(2):
            return "up" if await client.ping() else "down"
    except (OSError, RedisError):
        return "down"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        configure_logging()
        async with AsyncExitStack() as resources:
            engine = create_async_engine(settings.database_url)
            resources.push_async_callback(engine.dispose)
            redis = Redis.from_url(settings.redis_url)
            resources.push_async_callback(redis.aclose)
            application.state.db = engine
            application.state.redis = redis
            sessions = async_sessionmaker(engine, expire_on_commit=False)
            application.state.db_sessionmaker = sessions
            mqtt = MqttClient(settings)
            application.state.mqtt = mqtt
            publisher = application.state.mqtt_publisher = MqttPublisher(mqtt, sessions)
            handlers = MqttHandlers(sessions, redis, publisher)
            task = asyncio.create_task(
                mqtt.run(
                    {
                        "heartbeat": handlers.on_heartbeat,
                        "event": handlers.on_event,
                        "cmd/reply": handlers.on_cmd_reply,
                    }
                ),
                name="mqtt-subscriber",
            )
            try:
                yield
            finally:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

    application = FastAPI(title="银铃守护 API", version="1.0.0", lifespan=lifespan)
    application.state.settings = settings
    register_handlers(application)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Trace-Id"],
    )
    application.add_middleware(TraceMiddleware)
    application.include_router(router)
    if application.state.settings.app_env != "prod":
        application.include_router(mock_router, prefix=router.prefix)

    @application.get("/health", response_model=HealthResponse, response_model_by_alias=True)
    async def health(request: Request) -> dict:
        db, redis = await asyncio.gather(
            check_database(request.app.state.db), check_redis(request.app.state.redis)
        )
        mqtt = "up" if request.app.state.mqtt.connected else "down"
        return R.ok({"status": "up", "db": db, "redis": redis, "mqtt": mqtt})

    return application


app = create_app()

if __name__ == "__main__":
    loop = "asyncio:SelectorEventLoop" if sys.platform == "win32" else "auto"
    uvicorn.run(app, host="0.0.0.0", port=Settings().app_port, loop=loop)
