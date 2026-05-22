"""Create the initial 2.0.0 SQLite schema."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260522_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("value_json", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("key"),
    )

    op.create_table(
        "bundle_sets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("bundle_key", sa.String(length=120), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=True),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("manifest_path", sa.Text(), nullable=True),
        sa.Column("oid_index_path", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default=sa.text("'draft'"),
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bundle_key", name="uq_bundle_sets_bundle_key"),
        sa.UniqueConstraint("storage_path", name="uq_bundle_sets_storage_path"),
    )

    op.create_table(
        "bundle_modules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("bundle_set_id", sa.Integer(), nullable=False),
        sa.Column("module_name", sa.String(length=255), nullable=False),
        sa.Column("source_path", sa.Text(), nullable=True),
        sa.Column("compiled_path", sa.Text(), nullable=True),
        sa.Column("module_identity_oid", sa.String(length=255), nullable=True),
        sa.Column(
            "object_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "notification_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["bundle_set_id"], ["bundle_sets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "bundle_set_id",
            "module_name",
            name="uq_bundle_modules_bundle_set_module_name",
        ),
    )
    op.create_index(
        "ix_bundle_modules_bundle_set_id",
        "bundle_modules",
        ["bundle_set_id"],
        unique=False,
    )

    op.create_table(
        "compile_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("requested_mib_names_json", sa.JSON(), nullable=False),
        sa.Column("source_dirs_json", sa.JSON(), nullable=False),
        sa.Column("command_json", sa.JSON(), nullable=True),
        sa.Column("bundle_key", sa.String(length=120), nullable=True),
        sa.Column("output_dir", sa.Text(), nullable=True),
        sa.Column("manifest_path", sa.Text(), nullable=True),
        sa.Column("oid_index_path", sa.Text(), nullable=True),
        sa.Column("bundle_set_id", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("stdout_text", sa.Text(), nullable=True),
        sa.Column("stderr_text", sa.Text(), nullable=True),
        sa.Column("error_text", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["bundle_set_id"], ["bundle_sets.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_compile_runs_bundle_set_id",
        "compile_runs",
        ["bundle_set_id"],
        unique=False,
    )

    op.create_table(
        "bundle_objects",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("bundle_set_id", sa.Integer(), nullable=False),
        sa.Column("bundle_module_id", sa.Integer(), nullable=True),
        sa.Column("module_name", sa.String(length=255), nullable=False),
        sa.Column("object_name", sa.String(length=255), nullable=False),
        sa.Column("oid", sa.String(length=255), nullable=False),
        sa.Column("object_class", sa.String(length=64), nullable=True),
        sa.Column("object_type", sa.String(length=64), nullable=True),
        sa.Column("nodetype", sa.String(length=64), nullable=True),
        sa.Column("syntax", sa.String(length=255), nullable=True),
        sa.Column("max_access", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=True),
        sa.Column("index_json", sa.JSON(), nullable=True),
        sa.Column("augments", sa.String(length=255), nullable=True),
        sa.Column("constraints_json", sa.JSON(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("raw_json", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["bundle_set_id"], ["bundle_sets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["bundle_module_id"], ["bundle_modules.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "bundle_set_id",
            "module_name",
            "object_name",
            name="uq_bundle_objects_bundle_module_name",
        ),
    )
    op.create_index(
        "ix_bundle_objects_bundle_set_id",
        "bundle_objects",
        ["bundle_set_id"],
        unique=False,
    )
    op.create_index(
        "ix_bundle_objects_bundle_module_id",
        "bundle_objects",
        ["bundle_module_id"],
        unique=False,
    )
    op.create_index(
        "ix_bundle_objects_oid",
        "bundle_objects",
        ["oid"],
        unique=False,
    )

    op.create_table(
        "bundle_notifications",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("bundle_set_id", sa.Integer(), nullable=False),
        sa.Column("bundle_module_id", sa.Integer(), nullable=True),
        sa.Column("module_name", sa.String(length=255), nullable=False),
        sa.Column("notification_name", sa.String(length=255), nullable=False),
        sa.Column("oid", sa.String(length=255), nullable=False),
        sa.Column("object_class", sa.String(length=64), nullable=True),
        sa.Column("object_type", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("members_json", sa.JSON(), nullable=True),
        sa.Column("raw_json", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["bundle_set_id"], ["bundle_sets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["bundle_module_id"], ["bundle_modules.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "bundle_set_id",
            "module_name",
            "notification_name",
            name="uq_bundle_notifications_bundle_module_name",
        ),
    )
    op.create_index(
        "ix_bundle_notifications_bundle_set_id",
        "bundle_notifications",
        ["bundle_set_id"],
        unique=False,
    )
    op.create_index(
        "ix_bundle_notifications_bundle_module_id",
        "bundle_notifications",
        ["bundle_module_id"],
        unique=False,
    )
    op.create_index(
        "ix_bundle_notifications_oid",
        "bundle_notifications",
        ["oid"],
        unique=False,
    )

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
    op.create_index(
        "ix_notification_events_bundle_set_id",
        "notification_events",
        ["bundle_set_id"],
        unique=False,
    )
    op.create_index(
        "ix_notification_events_direction",
        "notification_events",
        ["direction"],
        unique=False,
    )
    op.create_index(
        "ix_notification_events_pdu_type",
        "notification_events",
        ["pdu_type"],
        unique=False,
    )
    op.create_index(
        "ix_notification_events_request_id",
        "notification_events",
        ["request_id"],
        unique=False,
    )
    op.create_index(
        "ix_notification_events_community",
        "notification_events",
        ["community"],
        unique=False,
    )
    op.create_index(
        "ix_notification_events_source_host",
        "notification_events",
        ["source_host"],
        unique=False,
    )
    op.create_index(
        "ix_notification_events_target_host",
        "notification_events",
        ["target_host"],
        unique=False,
    )
    op.create_index(
        "ix_notification_events_notification_oid",
        "notification_events",
        ["notification_oid"],
        unique=False,
    )
    op.create_index(
        "ix_notification_events_notification_name",
        "notification_events",
        ["notification_name"],
        unique=False,
    )
    op.create_index(
        "ix_notification_events_recorded_at",
        "notification_events",
        ["recorded_at"],
        unique=False,
    )

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

    op.create_table(
        "auth_sessions",
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=False),
        sa.Column(
            "issued_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("token"),
    )
    op.create_index(
        "ix_auth_sessions_username",
        "auth_sessions",
        ["username"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_auth_sessions_username", table_name="auth_sessions")
    op.drop_table("auth_sessions")

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

    op.drop_index("ix_bundle_notifications_oid", table_name="bundle_notifications")
    op.drop_index(
        "ix_bundle_notifications_bundle_module_id",
        table_name="bundle_notifications",
    )
    op.drop_index(
        "ix_bundle_notifications_bundle_set_id",
        table_name="bundle_notifications",
    )
    op.drop_table("bundle_notifications")

    op.drop_index("ix_bundle_objects_oid", table_name="bundle_objects")
    op.drop_index("ix_bundle_objects_bundle_module_id", table_name="bundle_objects")
    op.drop_index("ix_bundle_objects_bundle_set_id", table_name="bundle_objects")
    op.drop_table("bundle_objects")

    op.drop_index("ix_compile_runs_bundle_set_id", table_name="compile_runs")
    op.drop_table("compile_runs")

    op.drop_index("ix_bundle_modules_bundle_set_id", table_name="bundle_modules")
    op.drop_table("bundle_modules")
    op.drop_table("bundle_sets")
    op.drop_table("app_settings")
