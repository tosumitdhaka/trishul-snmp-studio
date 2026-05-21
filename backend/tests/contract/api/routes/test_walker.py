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


def test_walk_route_delegates_request_flags_and_returns_service_payload(isolated_db, monkeypatch):
    import app.services.runtime as runtime_module
    from app.api.routes import walker as walker_module

    token = _login_token()
    runtime = object()
    calls: list[dict[str, object]] = []

    async def fake_execute(**kwargs):
        calls.append(kwargs)
        if kwargs["parse"]:
            return {
                "mode": "parsed",
                "count": 1,
                "data": [{"symbolic": "SNMPv2-MIB::sysName.0"}],
            }
        return {
            "mode": "raw",
            "json_format": kwargs["json_format"],
            "data": ["1.3.6.1.2.1.1.5.0 = demo-agent"],
        }

    monkeypatch.setattr(runtime_module, "get_runtime_service", lambda: runtime)
    monkeypatch.setattr(walker_module.walker_service, "execute", fake_execute)

    parsed = asyncio.run(
        walker_module.execute_walk(
            walker_module.WalkBody(
                target="127.0.0.1",
                port=1161,
                community="public",
                oid="1.3.6.1.2.1.1",
                parse=True,
                use_mibs=True,
            ),
            x_auth_token=token,
        )
    )
    assert parsed["mode"] == "parsed"
    assert parsed["count"] == 1
    assert parsed["data"][0]["symbolic"] == "SNMPv2-MIB::sysName.0"

    raw = asyncio.run(
        walker_module.execute_walk(
            walker_module.WalkBody(
                target="127.0.0.1",
                port=1161,
                community="public",
                oid="SNMPv2-MIB::sysName",
                parse=False,
                use_mibs=False,
                json_format="grouped",
            ),
            x_auth_token=token,
        )
    )
    assert raw == {
        "mode": "raw",
        "json_format": "grouped",
        "data": ["1.3.6.1.2.1.1.5.0 = demo-agent"],
    }

    assert calls[0]["target"] == "127.0.0.1"
    assert calls[0]["parse"] is True
    assert calls[0]["use_mibs"] is True
    assert calls[0]["runtime_service"] is runtime
    assert calls[1]["oid"] == "SNMPv2-MIB::sysName"
    assert calls[1]["parse"] is False
    assert calls[1]["use_mibs"] is False
    assert calls[1]["json_format"] == "grouped"
    assert calls[1]["settings"] == isolated_db["settings"]


def test_walk_route_requires_auth_and_translates_service_errors(isolated_db, monkeypatch):
    import app.services.runtime as runtime_module
    from app.api.routes import walker as walker_module
    from app.services.walker_service import WalkerError

    del isolated_db

    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(
            walker_module.execute_walk(
                walker_module.WalkBody(
                    target="127.0.0.1",
                    port=1161,
                    community="public",
                    oid="1.3.6.1.2.1.1",
                ),
                x_auth_token=None,
            )
        )
    assert excinfo.value.status_code == 401

    async def fail_execute(**kwargs):
        del kwargs
        raise WalkerError("walk failed")

    monkeypatch.setattr(runtime_module, "get_runtime_service", lambda: object())
    monkeypatch.setattr(walker_module.walker_service, "execute", fail_execute)

    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(
            walker_module.execute_walk(
                walker_module.WalkBody(
                    target="127.0.0.1",
                    port=1161,
                    community="public",
                    oid="1.3.6.1.2.1.1",
                ),
                x_auth_token=_login_token(),
            )
        )
    assert excinfo.value.status_code == 400
    assert excinfo.value.detail == "walk failed"
