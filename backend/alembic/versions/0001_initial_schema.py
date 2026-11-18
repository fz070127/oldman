"""initial_schema

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "community",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("address", sa.String(length=255), nullable=False),
        sa.Column("contact_name", sa.String(length=32), nullable=True),
        sa.Column("contact_phone", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_community")),
    )
    op.create_table(
        "role",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=32), nullable=False),
        sa.Column(
            "permissions",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_role")),
        sa.UniqueConstraint("code", name="uq_role_code"),
    )
    op.create_table(
        "user",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("nickname", sa.String(length=32), nullable=False),
        sa.Column("phone", sa.String(length=64), nullable=True),
        sa.Column("avatar", sa.String(length=512), nullable=True),
        sa.Column("role_code", sa.String(length=32), nullable=False),
        sa.Column("community_id", sa.String(length=32), nullable=True),
        sa.Column("status", sa.SmallInteger(), server_default=sa.text("1"), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["community_id"], ["community.id"], name="fk_user_community_id"),
        sa.ForeignKeyConstraint(["role_code"], ["role.code"], name="fk_user_role_code"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user")),
        sa.UniqueConstraint("username", name="uq_user_username"),
    )
    op.create_table(
        "audit_log",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("actor_id", sa.String(length=32), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("target", sa.String(length=128), nullable=True),
        sa.Column(
            "detail",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["actor_id"], ["user.id"], name="fk_audit_log_actor_id"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_log")),
    )
    op.create_table(
        "guardian",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.String(length=32), nullable=False),
        sa.Column("community_id", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=32), nullable=False),
        sa.Column("phone", sa.String(length=64), nullable=False),
        sa.Column("elder_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.ForeignKeyConstraint(
            ["community_id"], ["community.id"], name="fk_guardian_community_id"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], name="fk_guardian_user_id"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_guardian")),
        sa.UniqueConstraint("user_id", name="uq_guardian_user_id"),
    )
    op.create_table(
        "notification",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.String(length=32), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=128), nullable=False),
        sa.Column("content", sa.String(length=512), nullable=False),
        sa.Column("biz_id", sa.String(length=32), nullable=True),
        sa.Column("read", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], name="fk_notification_user_id"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notification")),
    )
    op.create_table(
        "elder",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=32), nullable=False),
        sa.Column("gender", sa.SmallInteger(), nullable=False),
        sa.Column("birth_date", sa.Date(), nullable=False),
        sa.Column("phone", sa.String(length=64), nullable=True),
        sa.Column("community_id", sa.String(length=32), nullable=False),
        sa.Column("address", sa.String(length=255), nullable=False),
        sa.Column("room_no", sa.String(length=32), nullable=True),
        sa.Column("guardian_id", sa.String(length=32), nullable=True),
        sa.Column(
            "health_tags",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "emergency_contact",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("detect_mode", sa.SmallInteger(), server_default=sa.text("1"), nullable=False),
        sa.Column("status", sa.SmallInteger(), server_default=sa.text("1"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["community_id"], ["community.id"], name="fk_elder_community_id"),
        sa.ForeignKeyConstraint(["guardian_id"], ["guardian.id"], name="fk_elder_guardian_id"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_elder")),
    )
    op.create_table(
        "device",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("device_no", sa.String(length=64), nullable=False),
        sa.Column("elder_id", sa.String(length=32), nullable=True),
        sa.Column("type", sa.SmallInteger(), nullable=False),
        sa.Column("rtsp_url", sa.String(length=512), nullable=True),
        sa.Column("install_addr", sa.String(length=255), nullable=True),
        sa.Column("algo_version", sa.String(length=32), nullable=True),
        sa.Column(
            "config",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("status", sa.SmallInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_heartbeat", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["elder_id"], ["elder.id"], name="fk_device_elder_id"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_device")),
        sa.UniqueConstraint("device_no", name="uq_device_device_no"),
    )
    op.create_index("ix_device_last_heartbeat", "device", ["last_heartbeat"], unique=False)
    op.create_table(
        "family_binding",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("elder_id", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.String(length=32), nullable=False),
        sa.Column("relation", sa.String(length=32), nullable=False),
        sa.Column("is_primary", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("notify_order", sa.SmallInteger(), server_default=sa.text("1"), nullable=False),
        sa.ForeignKeyConstraint(["elder_id"], ["elder.id"], name="fk_family_binding_elder_id"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], name="fk_family_binding_user_id"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_family_binding")),
        sa.UniqueConstraint("elder_id", "user_id", name="uq_family_binding_elder_user"),
    )
    op.create_table(
        "event",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("device_id", sa.String(length=32), nullable=False),
        sa.Column("elder_id", sa.String(length=32), nullable=False),
        sa.Column("type", sa.String(length=16), nullable=False),
        sa.Column("level", sa.String(length=4), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=4, scale=3), nullable=False),
        sa.Column(
            "features",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("snapshot_url", sa.String(length=512), nullable=True),
        sa.Column("clip_url", sa.String(length=512), nullable=True),
        sa.Column("algo_version", sa.String(length=32), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("handled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("handle_result", sa.String(length=16), nullable=True),
        sa.ForeignKeyConstraint(["device_id"], ["device.id"], name="fk_event_device_id"),
        sa.ForeignKeyConstraint(["elder_id"], ["elder.id"], name="fk_event_elder_id"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_event")),
        sa.UniqueConstraint("event_id", name="uq_event_event_id"),
    )
    op.create_index(
        "ix_event_device_occurred_at",
        "event",
        ["device_id", sa.literal_column("occurred_at DESC")],
        unique=False,
    )
    op.create_index(
        "ix_event_elder_occurred_at",
        "event",
        ["elder_id", sa.literal_column("occurred_at DESC")],
        unique=False,
    )
    op.create_table(
        "alarm",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("event_id", sa.String(length=32), nullable=False),
        sa.Column("elder_id", sa.String(length=32), nullable=False),
        sa.Column("level", sa.String(length=4), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("current_handler", sa.String(length=32), nullable=True),
        sa.Column("escalate_step", sa.SmallInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ack_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("response_sec", sa.Integer(), nullable=True),
        sa.Column("remark", sa.String(length=512), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["current_handler"], ["user.id"], name="fk_alarm_current_handler"),
        sa.ForeignKeyConstraint(["elder_id"], ["elder.id"], name="fk_alarm_elder_id"),
        sa.ForeignKeyConstraint(["event_id"], ["event.id"], name="fk_alarm_event_id"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_alarm")),
        sa.UniqueConstraint("event_id", name="uq_alarm_event_id"),
    )
    op.create_index(
        "ix_alarm_elder_created_at",
        "alarm",
        ["elder_id", sa.literal_column("created_at DESC")],
        unique=False,
    )
    op.create_index(
        "ix_alarm_status_created_at",
        "alarm",
        ["status", sa.literal_column("created_at DESC")],
        unique=False,
    )
    op.create_table(
        "alarm_action",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("alarm_id", sa.String(length=32), nullable=False),
        sa.Column("actor_id", sa.String(length=32), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("channel", sa.String(length=16), nullable=True),
        sa.Column("result", sa.String(length=16), nullable=True),
        sa.Column(
            "detail",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["actor_id"], ["user.id"], name="fk_alarm_action_actor_id"),
        sa.ForeignKeyConstraint(["alarm_id"], ["alarm.id"], name="fk_alarm_action_alarm_id"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_alarm_action")),
    )
    op.create_index(
        "ix_alarm_action_alarm_created_at", "alarm_action", ["alarm_id", "created_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_alarm_action_alarm_created_at", table_name="alarm_action")
    op.drop_table("alarm_action")
    op.drop_index("ix_alarm_status_created_at", table_name="alarm")
    op.drop_index("ix_alarm_elder_created_at", table_name="alarm")
    op.drop_table("alarm")
    op.drop_index("ix_event_elder_occurred_at", table_name="event")
    op.drop_index("ix_event_device_occurred_at", table_name="event")
    op.drop_table("event")
    op.drop_table("family_binding")
    op.drop_index("ix_device_last_heartbeat", table_name="device")
    op.drop_table("device")
    op.drop_table("elder")
    op.drop_table("notification")
    op.drop_table("guardian")
    op.drop_table("audit_log")
    op.drop_table("user")
    op.drop_table("role")
    op.drop_table("community")
