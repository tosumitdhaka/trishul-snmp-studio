from __future__ import annotations

import pytest
from fastapi import HTTPException

pytestmark = pytest.mark.contract


def _login(settings_module, *, username: str = "admin", password: str = "admin123") -> dict[str, str]:
    return settings_module.login(
        settings_module.LoginBody(username=username, password=password)
    )


def test_settings_routes_manage_session_and_app_preferences(isolated_db):
    from app.api.routes import settings as settings_module

    del isolated_db

    login = _login(settings_module)
    token = login["token"]
    assert login["username"] == "admin"

    assert settings_module.check_session(x_auth_token=token) == {
        "status": "authenticated",
        "user": "admin",
    }

    default_settings = settings_module.get_settings_app(x_auth_token=token)
    assert default_settings["session_timeout"] == 3600
    assert default_settings["mib_remote_sources"] == []

    updated_settings = settings_module.update_settings_app(
        settings_module.SettingsBody(
            auto_start_simulator=True,
            auto_start_trap_receiver=True,
            session_timeout=7200,
            mib_auto_fetch=True,
            mib_remote_sources=["https://example.invalid/@mib@"],
        ),
        x_auth_token=token,
    )
    assert updated_settings["session_timeout"] == 7200
    assert updated_settings["auto_start_simulator"] is True
    assert updated_settings["auto_start_trap_receiver"] is True
    assert updated_settings["mib_auto_fetch"] is True
    assert updated_settings["mib_remote_sources"] == ["https://example.invalid/@mib@"]
    assert updated_settings["restart_required"] is False

    assert settings_module.logout(x_auth_token=token) == {"status": "logged_out"}

    with pytest.raises(HTTPException) as excinfo:
        settings_module.check_session(x_auth_token=token)
    assert excinfo.value.status_code == 401


def test_update_auth_requires_reauthentication_and_new_credentials_work(isolated_db):
    from app.api.routes import settings as settings_module

    del isolated_db

    token = _login(settings_module)["token"]
    update = settings_module.update_auth(
        settings_module.AuthBody(
            current_password="admin123",
            username="ops",
            password="betterpass",
        ),
        x_auth_token=token,
    )
    assert update["reauth_required"] is True

    with pytest.raises(HTTPException) as excinfo:
        settings_module.get_settings_app(x_auth_token=token)
    assert excinfo.value.status_code == 401

    relogin = _login(settings_module, username="ops", password="betterpass")
    assert relogin["username"] == "ops"
    assert settings_module.check_session(x_auth_token=relogin["token"]) == {
        "status": "authenticated",
        "user": "ops",
    }


def test_session_routes_translate_service_errors(monkeypatch):
    from app.api.routes import settings as settings_module
    from app.services.session import SessionServiceError

    class FailingSessionService:
        def login(self, **kwargs):
            del kwargs
            raise SessionServiceError("login denied", status_code=401)

        def logout(self, **kwargs):
            del kwargs
            raise SessionServiceError("logout denied", status_code=403)

        def check(self, **kwargs):
            del kwargs
            raise SessionServiceError("session expired", status_code=401)

        def update_credentials(self, **kwargs):
            del kwargs
            raise SessionServiceError("credential conflict", status_code=409)

    monkeypatch.setattr(
        settings_module,
        "_session_service_factory",
        lambda: FailingSessionService(),
    )

    with pytest.raises(HTTPException) as excinfo:
        settings_module.login(settings_module.LoginBody(username="admin", password="bad"))
    assert excinfo.value.status_code == 401
    assert excinfo.value.detail == "login denied"

    with pytest.raises(HTTPException) as excinfo:
        settings_module.logout(x_auth_token="demo-token")
    assert excinfo.value.status_code == 403
    assert excinfo.value.detail == "logout denied"

    with pytest.raises(HTTPException) as excinfo:
        settings_module.check_session(x_auth_token="demo-token")
    assert excinfo.value.status_code == 401
    assert excinfo.value.detail == "session expired"

    with pytest.raises(HTTPException) as excinfo:
        settings_module.update_auth(
            settings_module.AuthBody(
                current_password="old",
                username="admin",
                password="newpass",
            ),
            x_auth_token="demo-token",
        )
    assert excinfo.value.status_code == 409
    assert excinfo.value.detail == "credential conflict"


def test_shell_health_probe_returns_ok():
    from app.api.routes import settings as settings_module

    assert settings_module.shell_health_probe() == {"status": "ok"}
