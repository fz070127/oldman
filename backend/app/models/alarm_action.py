from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AlarmAction(Base):
    __tablename__ = "alarm_action"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    alarm_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("alarm.id", name="fk_alarm_action_alarm_id")
    )
    actor_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("user.id", name="fk_alarm_action_actor_id")
    )
    action: Mapped[str] = mapped_column(String(32))
    channel: Mapped[str | None] = mapped_column(String(16))
    result: Mapped[str | None] = mapped_column(String(16))
    detail: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("ix_alarm_action_alarm_created_at", alarm_id, created_at),)
