from __future__ import annotations

import asyncio

import pytest

pytestmark = pytest.mark.unit


class _WalkerRuntimeStub:
    def __init__(self, *, result: dict[str, object] | None = None, error: Exception | None = None) -> None:
        self.result = result or {"varbinds": []}
        self.error = error
        self.calls: list[dict[str, object]] = []

    async def manager_walk(self, **kwargs) -> dict[str, object]:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.result


def test_walk_item_and_metric_helpers_handle_display_and_metric_edges():
    from app.services.walker_service import (
        _extract_value,
        _metric_value,
        _value_is_metric,
        _walk_compat_items,
        _walk_item,
    )

    entry_with_display = {
        "oid": "1.3.6.1.2.1.1.1.0",
        "value_type": "integer",
        "value": {"display": "friendly"},
        "display_value": "ignored",
    }
    assert _walk_item(entry_with_display, use_mibs=False) == {
        "oid": "1.3.6.1.2.1.1.1.0",
        "type": "integer",
        "value": "friendly",
    }
    assert _extract_value({"value": {"display": "shown"}}) == "shown"
    assert _extract_value({"display_value": "fallback"}) == "fallback"

    compat_items = _walk_compat_items(
        [
            {"symbolic": "", "oid": "", "value_type": "integer", "value": {"value": 1}},
            {
                "symbolic": "IF-MIB::ifSpeed",
                "oid": "1.3.6.1.2.1.2.2.1.5.2",
                "value_type": "integer",
                "value": {"value": 123},
            },
            {
                "symbolic": "IF-MIB::ifAlias.2",
                "oid": "1.3.6.1.2.1.2.2.1.18.2",
                "value_type": "integer",
                "value": {"value": True},
            },
            {
                "symbolic": "SNMPv2-MIB::sysUpTime.0",
                "oid": "1.3.6.1.2.1.1.3.0",
                "value_type": "timeticks",
                "value": {"value": 250},
            },
        ],
        target_host="lab-agent",
        root_oid="IF-MIB::ifTable",
        use_mibs=True,
    )
    metric_names = {item["metric_name"] for item in compat_items}
    assert {"ifSpeed", "sysUpTime"} <= metric_names
    assert any(
        item["labels"]["snmp_index"] == "2"
        for item in compat_items
        if item["metric_name"] == "ifSpeed"
    )
    assert any(item["value"] == 2.5 for item in compat_items if item["metric_name"] == "sysUpTime")

    assert _value_is_metric("ifIndex", "integer", 1) is False
    assert _value_is_metric("ifSpeed", "octet-string", "123") is False
    assert _value_is_metric("ifSpeed", "counter32", "123") is True
    assert _value_is_metric("ifAdminStatus", "integer", 1) is False
    assert _value_is_metric("ifOperStatus", "integer", 1) is False
    assert _value_is_metric("ifPhysAddress", "octet-string", "00:11") is False

    assert _metric_value("counter32", None) is None
    assert _metric_value("counter32", True) is None
    assert _metric_value("counter32", "") is None
    assert _metric_value("counter32", "no digits") is None
    assert _metric_value("counter32", "speed 77 bps") == 77
    assert _metric_value("timeticks", 150) == 1.5


def test_execute_covers_raw_parsed_grouped_and_label_modes(isolated_db, monkeypatch):
    from app.services import walker_service
    from app.services.state_store import StateStore, _WALK_OIDS_RETURNED_KEY, _WALKS_EXECUTED_KEY

    settings = isolated_db["settings"]
    state = StateStore(isolated_db["session_factory"])
    broadcasts: list[object] = []

    async def fake_broadcast_stats(*, settings):
        broadcasts.append(settings)

    monkeypatch.setattr(walker_service, "broadcast_stats", fake_broadcast_stats)

    runtime = _WalkerRuntimeStub(
        result={
            "varbinds": [
                {
                    "oid": "1.3.6.1.2.1.1.3.0",
                    "symbolic": "SNMPv2-MIB::sysUpTime.0",
                    "value_type": "timeticks",
                    "value": {"value": 250},
                },
                {
                    "oid": "1.3.6.1.2.1.2.2.1.5.2",
                    "symbolic": "IF-MIB::ifSpeed.2",
                    "value_type": "integer",
                    "value": {"value": 123},
                },
            ]
        }
    )

    raw = asyncio.run(
        walker_service.execute(
            target="127.0.0.1",
            port=161,
            community="public",
            oid="IF-MIB::ifTable",
            parse=False,
            use_mibs=True,
            json_format="grouped",
            settings=settings,
            state=state,
            runtime_service=runtime,
        )
    )
    assert raw["mode"] == "raw"
    assert raw["json_format"] == "grouped"
    assert raw["count"] == 2
    assert raw["data"][0].startswith("SNMPv2-MIB::sysUpTime.0 = ")

    parsed_grouped = asyncio.run(
        walker_service.execute(
            target="127.0.0.1",
            port=161,
            community="public",
            oid="IF-MIB::ifTable",
            parse=True,
            use_mibs=True,
            json_format="grouped",
            settings=settings,
            state=state,
            runtime_service=runtime,
        )
    )
    assert parsed_grouped["mode"] == "parsed"
    assert {item["metric_name"] for item in parsed_grouped["data"]} == {"sysUpTime", "ifSpeed"}

    parsed_oid = asyncio.run(
        walker_service.execute(
            target="127.0.0.1",
            port=161,
            community="public",
            oid="1.3.6.1.2.1.1",
            parse=True,
            use_mibs=False,
            json_format="current",
            settings=settings,
            state=state,
            runtime_service=runtime,
        )
    )
    assert parsed_oid["mode"] == "parsed"
    assert parsed_oid["json_format"] == "flat"
    assert parsed_oid["data"][0]["oid"] == "1.3.6.1.2.1.1.3.0"
    assert "symbolic" not in parsed_oid["data"][0]

    fallback_runtime = _WalkerRuntimeStub(
        result={
            "varbinds": [
                {
                    "oid": "1.3.6.1.2.1.2.2.1.18.2",
                    "symbolic": "IF-MIB::ifAlias.2",
                    "value_type": "octet-string",
                    "value": {"value": "uplink"},
                }
            ]
        }
    )
    label_mode = asyncio.run(
        walker_service.execute(
            target="127.0.0.1",
            port=161,
            community="public",
            oid="IF-MIB::ifTable",
            parse=True,
            use_mibs=True,
            json_format="grouped",
            settings=settings,
            state=state,
            runtime_service=fallback_runtime,
        )
    )
    assert label_mode["mode"] == "label"
    assert label_mode["count"] == 1
    assert label_mode["data"] == label_mode["rawLines"]

    assert state.counter(_WALKS_EXECUTED_KEY) == 4
    assert state.counter(_WALK_OIDS_RETURNED_KEY) == 7
    assert broadcasts == [settings, settings, settings, settings]


def test_execute_translates_runtime_errors(isolated_db):
    from app.services.runtime import RuntimeServiceError
    from app.services.state_store import StateStore
    from app.services.walker_service import WalkerError, execute

    runtime = _WalkerRuntimeStub(error=RuntimeServiceError("walk failed"))

    with pytest.raises(WalkerError, match="walk failed"):
        asyncio.run(
            execute(
                target="127.0.0.1",
                port=161,
                community="public",
                oid="1.3.6.1.2.1.1",
                parse=False,
                use_mibs=False,
                json_format="oid",
                settings=isolated_db["settings"],
                state=StateStore(isolated_db["session_factory"]),
                runtime_service=runtime,
            )
        )
