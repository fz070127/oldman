from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Event(Base):
    __tablename__ = "event"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(64))
    device_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("device.id", name="fk_event_device_id")
    )
    elder_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("elder.id", name="fk_event_elder_id")
    )
    type: Mapped[str] = mapped_column(String(16))
    level: Mapped[str] = mapped_column(String(4))
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3))
    features: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    snapshot_url: Mapped[str | None] = mapped_column(String(512))
    clip_url: Mapped[str | None] = mapped_column(String(512))
    algo_version: Mapped[str | None] = mapped_column(String(32))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    handled: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    handle_result: Mapped[str | None] = mapped_column(String(16))

    __table_args__ = (
        Index("ix_event_elder_occurred_at", elder_id, occurred_at.desc()),
        Index("ix_event_device_occurred_at", device_id, occurred_at.desc()),
        UniqueConstraint("event_id", name="uq_event_event_id"),
    )
