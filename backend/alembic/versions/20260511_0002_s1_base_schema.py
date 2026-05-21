"""Create the initial S1 SQLite base schema."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260511_0002"
down_revision = "20260511_0001"
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
        sa.ForeignKeyConstraint(
            ["bundle_set_id"],
            ["bundle_sets.id"],
            ondelete="CASCADE",
        ),
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


def downgrade() -> None:
    op.drop_index("ix_bundle_modules_bundle_set_id", table_name="bundle_modules")
    op.drop_table("bundle_modules")
    op.drop_table("bundle_sets")
    op.drop_table("app_settings")
