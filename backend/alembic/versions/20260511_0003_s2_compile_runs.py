"""Create compile-run tracking for bundle lifecycle operations."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260511_0003"
down_revision = "20260511_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
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
        sa.ForeignKeyConstraint(
            ["bundle_set_id"],
            ["bundle_sets.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_compile_runs_bundle_set_id",
        "compile_runs",
        ["bundle_set_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_compile_runs_bundle_set_id", table_name="compile_runs")
    op.drop_table("compile_runs")
