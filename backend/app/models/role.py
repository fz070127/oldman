from sqlalchemy import String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Role(Base):
    __tablename__ = "role"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    code: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(32))
    permissions: Mapped[list[str]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))

    __table_args__ = (UniqueConstraint("code", name="uq_role_code"),)
