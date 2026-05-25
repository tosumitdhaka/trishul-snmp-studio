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


def test_trap_routes_delegate_to_service_layer_and_manage_history(isolated_db, monkeypatch):
    from app.api.routes import traps as traps_module

    token = _login_token()
    settings = isolated_db["settings"]
    state = object()
    runtime = object()
    captured: dict[str, object] = {}
    broadcasts: list[object] = []

    monkeypatch.setattr(traps_module, "_ctx", lambda: (settings, state, runtime))
    monkeypatch.setattr(traps_module, "get_state_store", lambda: state)

    async def fake_get_status(*, state, runtime_service):
        captured["status"] = (state, runtime_service)
        return {"running": True, "port": 2162, "community": "public", "resolve_mibs": True}

    async def fake_start_listener(*, port, community, resolve_mibs, settings, state, runtime_service):
        captured["start"] = (port, community, resolve_mibs, settings, state, runtime_service)
        return {"status": "started"}

    async def fake_stop_listener(*, settings, state, runtime_service):
        captured["stop"] = (settings, state, runtime_service)
        return {"status": "stopped"}

    async def fake_send_trap(*, target, port, community, oid, varbinds, settings, runtime_service):
        captured["send"] = (target, port, community, oid, varbinds, settings, runtime_service)
        return {"status": "sent"}

    def fake_list_events(*, state, history_service, limit=100):
        captured["list"] = (state, history_service, limit)
        return {"data": [], "count": 0}

    def fake_clear_events(*, history_service):
        captured["clear"] = history_service
        return {"status": "cleared"}

    async def fake_broadcast_stats(*, settings):
        broadcasts.append(settings)

    monkeypatch.setattr(traps_module.traps_service, "get_status", fake_get_status)
    monkeypatch.setattr(traps_module.traps_service, "start_listener", fake_start_listener)
    monkeypatch.setattr(traps_module.traps_service, "stop_listener", fake_stop_listener)
    monkeypatch.setattr(traps_module.traps_service, "send_trap", fake_send_trap)
    monkeypatch.setattr(traps_module.traps_service, "list_events", fake_list_events)
    monkeypatch.setattr(traps_module.traps_service, "clear_events", fake_clear_events)
    monkeypatch.setattr(traps_module, "EventHistoryService", lambda runtime_settings: ("history", runtime_settings))
    monkeypatch.setattr(traps_module, "broadcast_stats", fake_broadcast_stats)

    status = asyncio.run(traps_module.get_trap_status(x_auth_token=token))
    assert status["running"] is True
    assert captured["status"] == (state, runtime)

    started = asyncio.run(
        traps_module.start_trap_listener(
            traps_module.TrapListenerBody(port=2162, community="public", resolve_mibs=True),
            x_auth_token=token,
        )
    )
    assert started == {"status": "started"}
    assert captured["start"] == (2162, "public", True, settings, state, runtime)

    stopped = asyncio.run(traps_module.stop_trap_listener(x_auth_token=token))
    assert stopped == {"status": "stopped"}
    assert captured["stop"] == (settings, state, runtime)

    sent = asyncio.run(
        traps_module.send_trap(
            traps_module.TrapSendBody(
                target="127.0.0.1",
                port=2162,
                community="public",
                oid="1.3.6.1.6.3.1.1.5.3",
                varbinds=[
                    traps_module.TrapVarBindBody(
                        oid="1.3.6.1.2.1.1.3.0",
                        type="TimeTicks",
                        value=321,
                    )
                ],
            ),
            x_auth_token=token,
        )
    )
    assert sent == {"status": "sent"}
    assert captured["send"] == (
        "127.0.0.1",
        2162,
        "public",
        "1.3.6.1.6.3.1.1.5.3",
        [{"oid": "1.3.6.1.2.1.1.3.0", "type": "TimeTicks", "value": 321}],
        settings,
        runtime,
    )

    listed = traps_module.list_traps(x_auth_token=token)
    assert listed == {"data": [], "count": 0}
    assert captured["list"] == (state, ("history", settings), 100)

    cleared = asyncio.run(traps_module.clear_traps(x_auth_token=token))
    assert cleared == {"status": "cleared"}
    assert captured["clear"] == ("history", settings)
    assert broadcasts == [settings]


def test_trap_send_route_rejects_invalid_object_identifier_values(isolated_db, monkeypatch):
    from app.api.routes import traps as traps_module

    monkeypatch.setattr(
        traps_module,
        "_ctx",
        lambda: (isolated_db["settings"], object(), object()),
    )

    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(
            traps_module.send_trap(
                traps_module.TrapSendBody(
                    target="127.0.0.1",
                    port=2162,
                    community="public",
                    oid="1.3.6.1.6.3.1.1.5.3",
                    varbinds=[
                        traps_module.TrapVarBindBody(
                            oid="1.3.6.1.2.1.1.3.0",
                            type="OID",
                            value="1",
                        )
                    ],
                ),
                x_auth_token=_login_token(),
            )
        )

    assert excinfo.value.status_code == 400
    assert "VarBind 1 value" in excinfo.value.detail


def test_trap_routes_require_auth_and_update_resolve_mibs(isolated_db, monkeypatch):
    from app.api.routes import traps as traps_module
    from app.services.state_store import _TRAP_RESOLVE_MIBS_KEY, get_state_store

    broadcasts: list[object] = []

    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(traps_module.get_trap_status(x_auth_token=None))
    assert excinfo.value.status_code == 401

    monkeypatch.setattr(
        traps_module,
        "_ctx",
        lambda: (isolated_db["settings"], get_state_store(), object()),
    )
    async def fake_broadcast_status(*, settings):
        broadcasts.append(settings)

    monkeypatch.setattr(traps_module, "broadcast_status", fake_broadcast_status)

    payload = asyncio.run(
        traps_module.set_resolve_mibs(
            traps_module.TrapResolveMibsBody(resolve_mibs=False),
            x_auth_token=_login_token(),
        )
    )
    assert payload == {"resolve_mibs": False}
    assert get_state_store().snapshot()[_TRAP_RESOLVE_MIBS_KEY] is False
    assert broadcasts == [isolated_db["settings"]]
