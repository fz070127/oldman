from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class MqttCmdLog(Base):
    __tablename__ = "mqtt_cmd_log"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    device_no: Mapped[str] = mapped_column(String(64))
    cmd: Mapped[str] = mapped_column(String(16))
    payload: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(16))
    reply_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
