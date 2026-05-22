from __future__ import annotations

import json
import sqlite3

import pytest

pytestmark = pytest.mark.integration


def test_upgrade_database_creates_current_schema_and_preserves_rows(monkeypatch, tmp_path):
    from app.core.config import get_settings, reset_settings_cache
    from app.db.migrations import upgrade_database
    from app.db.session import reset_db_runtime
    from app.services.runtime import reset_runtime_service

    data_dir = tmp_path / "upgrade-data"
    monkeypatch.setenv("TRISHUL_DATA_DIR", str(data_dir))
    monkeypatch.delenv("DATABASE_URL", raising=False)

    reset_settings_cache()
    reset_db_runtime()
    reset_runtime_service()

    settings = get_settings()
    try:
        upgrade_database()

        with sqlite3.connect(settings.db_path) as connection:
            connection.execute(
                "INSERT INTO app_settings (key, value_json) VALUES (?, ?)",
                ("session_timeout_seconds", json.dumps(900)),
            )
            connection.commit()

        upgrade_database()

        with sqlite3.connect(settings.db_path) as connection:
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
            stored_value = connection.execute(
                "SELECT value_json FROM app_settings WHERE key = ?",
                ("session_timeout_seconds",),
            ).fetchone()

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
            "notification_event_search",
        } <= tables
        assert stored_value is not None
        assert int(stored_value[0]) == 900
    finally:
        reset_db_runtime()
        reset_settings_cache()
        reset_runtime_service()


def test_file_bootstrap_from_1x_layout_supports_v2_state(monkeypatch, tmp_path):
    from app.core.config import get_settings, reset_settings_cache
    from app.db.migrations import upgrade_database
    from app.db.session import create_session_factory, reset_db_runtime
    from app.models import AppSetting
    from app.services.app_settings import AppSettingsService
    from app.services.bundles import BundleService
    from app.services.history import EventHistoryService
    from app.services.runtime import reset_runtime_service
    from app.services.session import SessionService, SessionServiceError, reset_session_store

    data_dir = tmp_path / "bootstrap-data"
    config_dir = data_dir / "configs"
    bundles_dir = data_dir / "bundles"
    config_dir.mkdir(parents=True, exist_ok=True)
    bundles_dir.mkdir(parents=True, exist_ok=True)

    (config_dir / "secrets.json").write_text(
        json.dumps({"username": "bootstrap-admin", "password": "bootstrap-pass"})
    )
    (config_dir / "app_settings.json").write_text(
        json.dumps({"session_timeout_seconds": 999})
    )
    (data_dir / "traps.jsonl").write_text(json.dumps({"notification": "bootstrap"}) + "\n")
    (bundles_dir / "active_bundle.json").write_text(
        json.dumps({"bundle_set_id": 41, "bundle_key": "bootstrap-active"})
    )

    monkeypatch.setenv("TRISHUL_DATA_DIR", str(data_dir))
    monkeypatch.delenv("DATABASE_URL", raising=False)

    reset_settings_cache()
    reset_db_runtime()
    reset_runtime_service()

    settings = get_settings()
    try:
        upgrade_database()

        service = SessionService(settings)
        login_payload = service.login(username="bootstrap-admin", password="bootstrap-pass")
        assert login_payload["username"] == "bootstrap-admin"

        status = service.get_status(token=login_payload["token"])
        assert status["configured_username"] == "bootstrap-admin"
        assert status["credential_store"] == "sqlite:app_settings"
        assert status["session_store"] == "sqlite:auth_sessions"

        with pytest.raises(SessionServiceError) as default_login_exc:
            service.login(username="admin", password="admin123")
        assert default_login_exc.value.status_code == 401

        with create_session_factory(settings.database_url)() as session:
            stored_username = session.get(AppSetting, "auth.username")
            stored_password = session.get(AppSetting, "auth.password_hash")

            assert stored_username is not None
            assert stored_password is not None
            assert stored_username.value_json == "bootstrap-admin"
            assert stored_password.value_json != "bootstrap-pass"
            assert "$" in str(stored_password.value_json)

        settings.secrets_file.unlink()
        reset_session_store(settings)

        relogin_payload = service.login(username="bootstrap-admin", password="bootstrap-pass")
        assert relogin_payload["username"] == "bootstrap-admin"

        app_settings = AppSettingsService(settings).get_values()
        assert app_settings["session_timeout_seconds"] == settings.session_timeout

        history = EventHistoryService(settings).list_events()
        assert history["total"] == 0

        bundle_state = BundleService(settings).list_state()
        assert bundle_state["active_bundle_id"] is None
        assert bundle_state["active_pointer"] is None
    finally:
        reset_db_runtime()
        reset_settings_cache()
        reset_runtime_service()
