"""Store MQTT commands and their outcomes."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mqtt_cmd_log",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("device_no", sa.String(64), nullable=False),
        sa.Column("cmd", sa.String(16), nullable=False),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("reply_message", sa.Text),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_table("mqtt_cmd_log")
