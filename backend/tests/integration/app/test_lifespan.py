from __future__ import annotations

import anyio
import pytest
from sqlalchemy import inspect

pytestmark = pytest.mark.integration


def test_lifespan_bootstraps_empty_db(monkeypatch, tmp_path):
    from app.core.config import reset_settings_cache
    from app.db.session import get_engine, reset_db_runtime
    from app.main import create_app

    data_dir = tmp_path / "app-data"

    monkeypatch.setenv("TRISHUL_DATA_DIR", str(data_dir))
    monkeypatch.delenv("DATABASE_URL", raising=False)

    reset_settings_cache()
    reset_db_runtime()

    app = create_app()

    async def run_lifespan() -> None:
        async with app.router.lifespan_context(app):
            pass

    anyio.run(run_lifespan)

    database_path = data_dir / "trishul_v2.sqlite3"
    assert database_path.exists()

    inspector = inspect(get_engine())
    assert {
        "alembic_version",
        "app_settings",
        "auth_sessions",
        "bundle_sets",
        "bundle_modules",
        "bundle_objects",
        "bundle_notifications",
        "compile_runs",
        "notification_events",
    } <= set(inspector.get_table_names())

    reset_db_runtime()
    reset_settings_cache()


def test_lifespan_autostarts_services_from_saved_settings(
    isolated_db,
    monkeypatch,
):
    from app.main import create_app
    from app.models import AppSetting
    from app.services.state_store import (
        _AUTO_START_SIMULATOR_KEY,
        _AUTO_START_TRAP_RECEIVER_KEY,
        _LISTENER_COMMUNITY_KEY,
        _LISTENER_PORT_KEY,
        _SIMULATOR_COMMUNITY_KEY,
        _SIMULATOR_PORT_KEY,
        _TRAP_RESOLVE_MIBS_KEY,
    )

    session_factory = isolated_db["session_factory"]

    with session_factory() as session:
        session.add_all(
            [
                AppSetting(key=_AUTO_START_SIMULATOR_KEY, value_json=True),
                AppSetting(key=_AUTO_START_TRAP_RECEIVER_KEY, value_json=True),
                AppSetting(key=_SIMULATOR_PORT_KEY, value_json=21061),
                AppSetting(key=_SIMULATOR_COMMUNITY_KEY, value_json="lab"),
                AppSetting(key=_LISTENER_PORT_KEY, value_json=21162),
                AppSetting(key=_LISTENER_COMMUNITY_KEY, value_json="traps"),
                AppSetting(key=_TRAP_RESOLVE_MIBS_KEY, value_json=False),
            ]
        )
        session.commit()

    class StubRuntimeService:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict[str, object]]] = []
            self.responder = {
                "running": False,
                "host": None,
                "port": None,
                "communities": None,
                "bundle_set_id": None,
                "stale_bundle": False,
                "local_address": None,
                "last_error": None,
                "configured_object_count": 0,
                "configured_objects": [],
                "configured_rule_count": 0,
                "configured_rules": [],
                "request_count": 0,
                "last_activity": None,
            }
            self.listener = {
                "running": False,
                "host": None,
                "port": None,
                "communities": None,
                "bundle_set_id": None,
                "stale_bundle": False,
                "local_address": None,
                "last_error": None,
                "configured_object_count": None,
                "configured_objects": None,
                "configured_rule_count": None,
                "configured_rules": None,
            }

        async def get_state(self):
            return {
                "active_bundle": {"id": 1},
                "responder": dict(self.responder),
                "notifications": {
                    "listener": dict(self.listener),
                    "recent_event_count": 0,
                    "last_event": None,
                },
            }

        async def start_responder(self, **kwargs):
            self.calls.append(("start_responder", kwargs))
            self.responder.update(
                {
                    "running": True,
                    "host": kwargs["host"],
                    "port": kwargs["port"],
                    "communities": kwargs["communities"],
                    "configured_object_count": len(kwargs.get("objects") or []),
                    "configured_objects": kwargs.get("objects") or [],
                }
            )
            return {"operation": "start_responder"}

        async def start_listener(self, **kwargs):
            self.calls.append(("start_listener", kwargs))
            self.listener.update(
                {
                    "running": True,
                    "host": kwargs["host"],
                    "port": kwargs["port"],
                    "communities": kwargs["communities"],
                }
            )
            return {"operation": "start_listener"}

    stub_runtime = StubRuntimeService()
    import app.services.runtime as runtime_module

    monkeypatch.setattr(runtime_module, "get_runtime_service", lambda: stub_runtime)

    app = create_app()

    async def run_lifespan() -> None:
        async with app.router.lifespan_context(app):
            pass

    anyio.run(run_lifespan)

    start_responder_call = next(
        payload for name, payload in stub_runtime.calls if name == "start_responder"
    )
    assert start_responder_call["port"] == 21061
    assert start_responder_call["communities"] == ["lab"]

    start_listener_call = next(
        payload for name, payload in stub_runtime.calls if name == "start_listener"
    )
    assert start_listener_call["port"] == 21162
    assert start_listener_call["communities"] == ["traps"]
