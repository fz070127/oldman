from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    app_port: int = Field(default=8000, ge=1, le=65535)
    database_url: str = "postgresql+asyncpg://postgres@127.0.0.1:5432/silver_bell"
    redis_url: str = "redis://127.0.0.1:6379/0"
    jwt_secret: SecretStr = SecretStr("")
    jwt_alg: str = "HS256"
    access_token_expire_min: int = Field(default=30, gt=0)
    refresh_token_expire_day: int = Field(default=7, gt=0)
    minio_endpoint: str = "127.0.0.1:9000"
    minio_ak: SecretStr = SecretStr("")
    minio_sk: SecretStr = SecretStr("")
    minio_bucket: str = "silver-bell"
    mqtt_host: str = "127.0.0.1"
    mqtt_port: int = Field(default=1883, ge=1, le=65535)
    mqtt_user: str = ""
    mqtt_pass: SecretStr = SecretStr("")
    notify_provider: Literal["mock", "aliyun"] = "mock"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
