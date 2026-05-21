from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

pytestmark = pytest.mark.contract


def _login_token() -> str:
    from app.api.routes import settings as settings_module

    return settings_module.login(
        settings_module.LoginBody(username="admin", password="admin123")
    )["token"]


def test_stats_routes_delegate_to_service_layer_and_broadcast(isolated_db, monkeypatch):
    import app.services.runtime as runtime_module
    from app.api.routes import stats as stats_module

    token = _login_token()
    settings = isolated_db["settings"]
    runtime = object()
    captured: dict[str, object] = {}
    broadcasts: list[object] = []

    monkeypatch.setattr(runtime_module, "get_runtime_service", lambda: runtime)
    monkeypatch.setattr(stats_module, "EventHistoryService", lambda runtime_settings: ("history", runtime_settings))

    async def fake_get_stats(*, state, history_service, runtime_service, settings):
        captured["get"] = (state, history_service, runtime_service, settings)
        return {"walker": {"walks_executed": 3}}

    async def fake_reset_stats(*, state, history_service, runtime_service):
        captured["reset"] = (state, history_service, runtime_service)
        return {"status": "reset"}

    async def fake_broadcast_stats(*, settings):
        broadcasts.append(settings)

    monkeypatch.setattr(stats_module.stats_service, "get_stats", fake_get_stats)
    monkeypatch.setattr(stats_module.stats_service, "reset_stats", fake_reset_stats)
    monkeypatch.setattr(stats_module, "broadcast_stats", fake_broadcast_stats)

    stats = asyncio.run(stats_module.get_stats(x_auth_token=token))
    assert stats == {"walker": {"walks_executed": 3}}
    assert captured["get"][1] == ("history", settings)
    assert captured["get"][2] is runtime
    assert captured["get"][3] == settings

    reset = asyncio.run(stats_module.reset_stats(x_auth_token=token))
    assert reset == {"status": "reset"}
    assert captured["reset"][1] == ("history", settings)
    assert captured["reset"][2] is runtime
    assert broadcasts == [settings]


def test_stats_routes_require_auth(isolated_db):
    from app.api.routes import stats as stats_module

    del isolated_db

    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(stats_module.get_stats(x_auth_token=None))
    assert excinfo.value.status_code == 401
