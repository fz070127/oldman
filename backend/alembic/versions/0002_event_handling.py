"""Persist event handling metadata independently of an alarm."""

import sqlalchemy as sa

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("event", sa.Column("handle_remark", sa.String(512), nullable=True))
    op.add_column("event", sa.Column("handled_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("event", "handled_at")
    op.drop_column("event", "handle_remark")
