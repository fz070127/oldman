from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Alarm(Base):
    __tablename__ = "alarm"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    event_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("event.id", name="fk_alarm_event_id")
    )
    elder_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("elder.id", name="fk_alarm_elder_id")
    )
    level: Mapped[str] = mapped_column(String(4))
    status: Mapped[str] = mapped_column(String(24))
    current_handler: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("user.id", name="fk_alarm_current_handler")
    )
    escalate_step: Mapped[int] = mapped_column(SmallInteger, server_default=text("0"))
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ack_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    response_sec: Mapped[int | None] = mapped_column(Integer)
    remark: Mapped[str | None] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_alarm_status_created_at", status, created_at.desc()),
        Index("ix_alarm_elder_created_at", elder_id, created_at.desc()),
        UniqueConstraint("event_id", name="uq_alarm_event_id"),
    )
