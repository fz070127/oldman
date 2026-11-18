from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, SmallInteger, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Elder(Base):
    __tablename__ = "elder"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(32))
    gender: Mapped[int] = mapped_column(SmallInteger)
    birth_date: Mapped[date] = mapped_column(Date)
    phone: Mapped[str | None] = mapped_column(String(64))
    community_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("community.id", name="fk_elder_community_id")
    )
    address: Mapped[str] = mapped_column(String(255))
    room_no: Mapped[str | None] = mapped_column(String(32))
    guardian_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("guardian.id", name="fk_elder_guardian_id")
    )
    health_tags: Mapped[list[str]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    emergency_contact: Mapped[list[dict]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    detect_mode: Mapped[int] = mapped_column(SmallInteger, server_default=text("1"))
    status: Mapped[int] = mapped_column(SmallInteger, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
