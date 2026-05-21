"""Persistent key-value state store backed by AppSetting DB rows.

Module-level singleton — call get_state_store() to get the instance.
Call init_state_store(settings) at app startup.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.models import AppSetting

_AUTO_START_SIMULATOR_KEY = "settings.auto_start_simulator"
_AUTO_START_TRAP_RECEIVER_KEY = "settings.auto_start_trap_receiver"
_MIB_AUTO_FETCH_KEY = "settings.mib_auto_fetch"
_MIB_REMOTE_SOURCES_KEY = "settings.mib_remote_sources"
_TRAP_RESOLVE_MIBS_KEY = "settings.trap_resolve_mibs"
_SIMULATOR_PORT_KEY = "settings.simulator_port"
_SIMULATOR_COMMUNITY_KEY = "settings.simulator_community"
_LISTENER_PORT_KEY = "settings.listener_port"
_LISTENER_COMMUNITY_KEY = "settings.listener_community"
_SIMULATOR_STARTED_AT_KEY = "runtime.simulator_started_at"
_LISTENER_STARTED_AT_KEY = "runtime.listener_started_at"
_STATS_RESET_AT_KEY = "stats.reset_at"
_WALKS_EXECUTED_KEY = "stats.walks_executed"
_WALK_OIDS_RETURNED_KEY = "stats.walk_oids_returned"
_MIB_RELOAD_COUNT_KEY = "stats.mib_reload_count"

_DEFAULTS: dict[str, Any] = {
    _AUTO_START_SIMULATOR_KEY: False,
    _AUTO_START_TRAP_RECEIVER_KEY: False,
    _MIB_AUTO_FETCH_KEY: False,
    _MIB_REMOTE_SOURCES_KEY: [],
    _TRAP_RESOLVE_MIBS_KEY: True,
    _SIMULATOR_PORT_KEY: 1061,
    _SIMULATOR_COMMUNITY_KEY: "public",
    _LISTENER_PORT_KEY: 1162,
    _LISTENER_COMMUNITY_KEY: "public",
    _SIMULATOR_STARTED_AT_KEY: None,
    _LISTENER_STARTED_AT_KEY: None,
    _STATS_RESET_AT_KEY: None,
    _WALKS_EXECUTED_KEY: 0,
    _WALK_OIDS_RETURNED_KEY: 0,
    _MIB_RELOAD_COUNT_KEY: 0,
}


class StateStore:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def snapshot(self) -> dict[str, Any]:
        with self._session_factory() as session:
            values = dict(_DEFAULTS)
            for key in _DEFAULTS:
                row = session.get(AppSetting, key)
                if row is not None:
                    values[key] = row.value_json
            return values

    def get_value(self, key: str, default: Any = None) -> Any:
        fallback = _DEFAULTS.get(key, default)
        with self._session_factory() as session:
            row = session.get(AppSetting, key)
            return fallback if row is None else row.value_json

    def set_value(self, key: str, value: Any) -> None:
        with self._session_factory() as session:
            row = session.get(AppSetting, key)
            if row is None:
                row = AppSetting(key=key, value_json=value)
                session.add(row)
            else:
                row.value_json = value
            session.commit()

    def counter(self, key: str) -> int:
        raw = self.get_value(key, 0)
        try:
            return max(0, int(raw or 0))
        except (TypeError, ValueError):
            return 0

    def increment_counter(self, key: str, amount: int = 1) -> int:
        with self._session_factory() as session:
            row = session.get(AppSetting, key)
            current = 0
            if row is not None:
                try:
                    current = int(row.value_json or 0)
                except (TypeError, ValueError):
                    pass
            updated = max(0, current + int(amount or 0))
            if row is None:
                session.add(AppSetting(key=key, value_json=updated))
            else:
                row.value_json = updated
            session.commit()
            return updated

    def uptime_seconds(self, key: str) -> int | None:
        started_at = self.get_value(key)
        if not isinstance(started_at, str) or not started_at:
            return None
        try:
            started = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        except ValueError:
            return None
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        return max(0, int((datetime.now(timezone.utc) - started).total_seconds()))

    @staticmethod
    def coerce_port(raw: Any, *, default: int) -> int:
        try:
            v = int(raw)
            return v if 1 <= v <= 65535 else default
        except (TypeError, ValueError):
            return default

    @staticmethod
    def coerce_community(raw: Any, *, default: str) -> str:
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
        return default


_store: StateStore | None = None


def init_state_store(session_factory) -> StateStore:
    global _store
    _store = StateStore(session_factory)
    return _store


def get_state_store() -> StateStore:
    if _store is not None:
        return _store
    # Auto-initialize from current settings when called before explicit init
    from app.core.config import get_settings
    from app.db.session import create_session_factory
    settings = get_settings()
    return init_state_store(create_session_factory(settings.database_url))


def reset_state_store() -> None:
    global _store
    _store = None
