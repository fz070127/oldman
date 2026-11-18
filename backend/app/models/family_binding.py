from sqlalchemy import Boolean, ForeignKey, SmallInteger, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class FamilyBinding(Base):
    __tablename__ = "family_binding"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    elder_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("elder.id", name="fk_family_binding_elder_id")
    )
    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("user.id", name="fk_family_binding_user_id")
    )
    relation: Mapped[str] = mapped_column(String(32))
    is_primary: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    notify_order: Mapped[int] = mapped_column(SmallInteger, server_default=text("1"))

    __table_args__ = (UniqueConstraint("elder_id", "user_id", name="uq_family_binding_elder_user"),)
