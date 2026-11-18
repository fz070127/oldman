from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Notification(Base):
    __tablename__ = "notification"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("user.id", name="fk_notification_user_id")
    )
    type: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(128))
    content: Mapped[str] = mapped_column(String(512))
    biz_id: Mapped[str | None] = mapped_column(String(32))
    read: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
