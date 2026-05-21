"""Rename state-store app_setting keys to canonical namespaces."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260521_0007"
down_revision = "20260511_0006"
branch_labels = None
depends_on = None


KEY_RENAMES: tuple[tuple[str, str], ...] = (
    ("legacy.auto_start_simulator", "settings.auto_start_simulator"),
    ("legacy.auto_start_trap_receiver", "settings.auto_start_trap_receiver"),
    ("legacy.mib_auto_fetch", "settings.mib_auto_fetch"),
    ("legacy.mib_remote_sources", "settings.mib_remote_sources"),
    ("legacy.trap_resolve_mibs", "settings.trap_resolve_mibs"),
    ("legacy.simulator_port", "settings.simulator_port"),
    ("legacy.simulator_community", "settings.simulator_community"),
    ("legacy.listener_port", "settings.listener_port"),
    ("legacy.listener_community", "settings.listener_community"),
    ("legacy.simulator_started_at", "runtime.simulator_started_at"),
    ("legacy.listener_started_at", "runtime.listener_started_at"),
    ("legacy.stats_reset_at", "stats.reset_at"),
    ("legacy.stats.walks_executed", "stats.walks_executed"),
    ("legacy.stats.walk_oids_returned", "stats.walk_oids_returned"),
    ("legacy.stats.mib_reload_count", "stats.mib_reload_count"),
)


def _rename_keys(pairs: tuple[tuple[str, str], ...]) -> None:
    connection = op.get_bind()
    for old_key, new_key in pairs:
        old_exists = connection.execute(
            sa.text("SELECT 1 FROM app_settings WHERE key = :key"),
            {"key": old_key},
        ).scalar()
        if not old_exists:
            continue

        new_exists = connection.execute(
            sa.text("SELECT 1 FROM app_settings WHERE key = :key"),
            {"key": new_key},
        ).scalar()
        if new_exists:
            connection.execute(
                sa.text("DELETE FROM app_settings WHERE key = :key"),
                {"key": old_key},
            )
            continue

        connection.execute(
            sa.text("UPDATE app_settings SET key = :new_key WHERE key = :old_key"),
            {"old_key": old_key, "new_key": new_key},
        )


def upgrade() -> None:
    _rename_keys(KEY_RENAMES)


def downgrade() -> None:
    _rename_keys(tuple((new_key, old_key) for old_key, new_key in KEY_RENAMES))
