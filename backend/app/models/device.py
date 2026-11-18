from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Device(Base):
    __tablename__ = "device"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    device_no: Mapped[str] = mapped_column(String(64))
    elder_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("elder.id", name="fk_device_elder_id")
    )
    type: Mapped[int] = mapped_column(SmallInteger)
    rtsp_url: Mapped[str | None] = mapped_column(String(512))
    install_addr: Mapped[str | None] = mapped_column(String(255))
    algo_version: Mapped[str | None] = mapped_column(String(32))
    config: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    status: Mapped[int] = mapped_column(SmallInteger, server_default=text("0"))
    last_heartbeat: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_device_last_heartbeat", last_heartbeat),
        UniqueConstraint("device_no", name="uq_device_device_no"),
    )
