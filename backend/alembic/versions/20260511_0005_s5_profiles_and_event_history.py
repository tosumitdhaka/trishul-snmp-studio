"""Create durable notification event history."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260511_0005"
down_revision = "20260511_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notification_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("bundle_set_id", sa.Integer(), nullable=True),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("pdu_type", sa.String(length=32), nullable=False),
        sa.Column("request_id", sa.Integer(), nullable=True),
        sa.Column("community", sa.String(length=255), nullable=True),
        sa.Column("source_host", sa.String(length=255), nullable=True),
        sa.Column("source_port", sa.Integer(), nullable=True),
        sa.Column("target_host", sa.String(length=255), nullable=True),
        sa.Column("target_port", sa.Integer(), nullable=True),
        sa.Column("notification_oid", sa.String(length=255), nullable=True),
        sa.Column("notification_name", sa.String(length=255), nullable=True),
        sa.Column("notification_description", sa.Text(), nullable=True),
        sa.Column("uptime", sa.Integer(), nullable=True),
        sa.Column("payload_hex", sa.Text(), nullable=True),
        sa.Column("event_json", sa.JSON(), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["bundle_set_id"], ["bundle_sets.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notification_events_bundle_set_id", "notification_events", ["bundle_set_id"], unique=False)
    op.create_index("ix_notification_events_direction", "notification_events", ["direction"], unique=False)
    op.create_index("ix_notification_events_pdu_type", "notification_events", ["pdu_type"], unique=False)
    op.create_index("ix_notification_events_request_id", "notification_events", ["request_id"], unique=False)
    op.create_index("ix_notification_events_community", "notification_events", ["community"], unique=False)
    op.create_index("ix_notification_events_source_host", "notification_events", ["source_host"], unique=False)
    op.create_index("ix_notification_events_target_host", "notification_events", ["target_host"], unique=False)
    op.create_index("ix_notification_events_notification_oid", "notification_events", ["notification_oid"], unique=False)
    op.create_index("ix_notification_events_notification_name", "notification_events", ["notification_name"], unique=False)
    op.create_index("ix_notification_events_recorded_at", "notification_events", ["recorded_at"], unique=False)

    op.execute(
        """
        CREATE VIRTUAL TABLE notification_event_search
        USING fts5(
            event_id UNINDEXED,
            bundle_set_id UNINDEXED,
            direction UNINDEXED,
            pdu_type,
            community,
            source_host,
            target_host,
            notification_name,
            notification_oid,
            notification_description,
            event_text,
            tokenize = 'porter unicode61'
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE notification_event_search")
    op.drop_index("ix_notification_events_recorded_at", table_name="notification_events")
    op.drop_index("ix_notification_events_notification_name", table_name="notification_events")
    op.drop_index("ix_notification_events_notification_oid", table_name="notification_events")
    op.drop_index("ix_notification_events_target_host", table_name="notification_events")
    op.drop_index("ix_notification_events_source_host", table_name="notification_events")
    op.drop_index("ix_notification_events_community", table_name="notification_events")
    op.drop_index("ix_notification_events_request_id", table_name="notification_events")
    op.drop_index("ix_notification_events_pdu_type", table_name="notification_events")
    op.drop_index("ix_notification_events_direction", table_name="notification_events")
    op.drop_index("ix_notification_events_bundle_set_id", table_name="notification_events")
    op.drop_table("notification_events")
