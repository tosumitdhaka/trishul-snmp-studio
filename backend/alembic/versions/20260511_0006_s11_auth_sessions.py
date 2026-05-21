"""Create durable auth sessions for S11 runtime-state cleanup."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260511_0006"
down_revision = "20260511_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
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
    op.create_index("ix_auth_sessions_username", "auth_sessions", ["username"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_auth_sessions_username", table_name="auth_sessions")
    op.drop_table("auth_sessions")
