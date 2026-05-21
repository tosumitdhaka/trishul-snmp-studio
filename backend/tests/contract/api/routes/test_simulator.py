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


def test_simulator_routes_delegate_to_service_layer(isolated_db, monkeypatch):
    from app.api.routes import simulator as simulator_module

    token = _login_token()
    settings = isolated_db["settings"]
    state = object()
    runtime = object()
    captured: dict[str, object] = {}

    monkeypatch.setattr(simulator_module, "_ctx", lambda: (settings, state, runtime))

    def fake_get_custom_data(*, settings):
        captured["get_custom_data"] = settings
        return {"1.3.6.1.2.1.1.5.0": "demo-agent"}

    async def fake_save_custom_data(payload, *, settings, runtime_service):
        captured["save_custom_data"] = (payload, settings, runtime_service)
        return {"status": "saved"}

    async def fake_get_logs(*, limit, runtime_service):
        captured["get_logs"] = (limit, runtime_service)
        return {"total": 1, "limit": limit, "items": [{"request_type": "GETNEXT"}]}

    async def fake_clear_logs(*, runtime_service):
        captured["clear_logs"] = runtime_service
        return {"status": "cleared"}

    async def fake_start(*, port, community, settings, state, runtime_service):
        captured["start"] = (port, community, settings, state, runtime_service)
        return {"status": "started", "port": port, "community": community}

    async def fake_stop(*, settings, state, runtime_service):
        captured["stop"] = (settings, state, runtime_service)
        return {"status": "stopped"}

    async def fake_restart(*, settings, state, runtime_service):
        captured["restart"] = (settings, state, runtime_service)
        return {"status": "started"}

    async def fake_get_status(*, state, runtime_service):
        captured["status"] = (state, runtime_service)
        return {"running": True, "port": 1161, "community": "public"}

    monkeypatch.setattr(simulator_module.simulator_service, "get_custom_data", fake_get_custom_data)
    monkeypatch.setattr(simulator_module.simulator_service, "save_custom_data", fake_save_custom_data)
    monkeypatch.setattr(simulator_module.simulator_service, "get_logs", fake_get_logs)
    monkeypatch.setattr(simulator_module.simulator_service, "clear_logs", fake_clear_logs)
    monkeypatch.setattr(simulator_module.simulator_service, "start", fake_start)
    monkeypatch.setattr(simulator_module.simulator_service, "stop", fake_stop)
    monkeypatch.setattr(simulator_module.simulator_service, "restart", fake_restart)
    monkeypatch.setattr(simulator_module.simulator_service, "get_status", fake_get_status)

    assert simulator_module.get_simulator_data(x_auth_token=token) == {
        "1.3.6.1.2.1.1.5.0": "demo-agent"
    }
    assert captured["get_custom_data"] == settings

    saved = asyncio.run(
        simulator_module.save_simulator_data(
            {"1.3.6.1.2.1.1.5.0": "demo-agent"},
            x_auth_token=token,
        )
    )
    assert saved == {"status": "saved"}
    assert captured["save_custom_data"] == (
        {"1.3.6.1.2.1.1.5.0": "demo-agent"},
        settings,
        runtime,
    )

    logs = asyncio.run(simulator_module.get_simulator_logs(limit=25, x_auth_token=token))
    assert logs["limit"] == 25
    assert captured["get_logs"] == (25, runtime)

    assert asyncio.run(simulator_module.clear_simulator_logs(x_auth_token=token)) == {
        "status": "cleared"
    }
    assert captured["clear_logs"] == runtime

    started = asyncio.run(
        simulator_module.start_simulator(
            simulator_module.SimulatorStartBody(port=1161, community="public"),
            x_auth_token=token,
        )
    )
    assert started == {"status": "started", "port": 1161, "community": "public"}
    assert captured["start"] == (1161, "public", settings, state, runtime)

    assert asyncio.run(simulator_module.stop_simulator(x_auth_token=token)) == {"status": "stopped"}
    assert captured["stop"] == (settings, state, runtime)

    assert asyncio.run(simulator_module.restart_simulator(x_auth_token=token)) == {"status": "started"}
    assert captured["restart"] == (settings, state, runtime)

    assert asyncio.run(simulator_module.get_simulator_status(x_auth_token=token)) == {
        "running": True,
        "port": 1161,
        "community": "public",
    }
    assert captured["status"] == (state, runtime)


def test_simulator_routes_require_auth_and_translate_service_errors(isolated_db, monkeypatch):
    from app.api.routes import simulator as simulator_module
    from app.services.simulator_service import SimulatorError

    with pytest.raises(HTTPException) as excinfo:
        simulator_module.get_simulator_data(x_auth_token=None)
    assert excinfo.value.status_code == 401

    monkeypatch.setattr(
        simulator_module,
        "_ctx",
        lambda: (isolated_db["settings"], object(), object()),
    )

    async def fail_start(**kwargs):
        del kwargs
        raise SimulatorError("start failed")

    monkeypatch.setattr(simulator_module.simulator_service, "start", fail_start)

    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(
            simulator_module.start_simulator(
                simulator_module.SimulatorStartBody(port=1161, community="public"),
                x_auth_token=_login_token(),
            )
        )
    assert excinfo.value.status_code == 400
    assert excinfo.value.detail == "start failed"
