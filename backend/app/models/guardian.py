from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Guardian(Base):
    __tablename__ = "guardian"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("user.id", name="fk_guardian_user_id")
    )
    community_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("community.id", name="fk_guardian_community_id")
    )
    name: Mapped[str] = mapped_column(String(32))
    phone: Mapped[str] = mapped_column(String(64))
    elder_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))

    __table_args__ = (UniqueConstraint("user_id", name="uq_guardian_user_id"),)
