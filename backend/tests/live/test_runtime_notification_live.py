from __future__ import annotations

import asyncio
import os
import socket

import pytest

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        os.getenv("TRISHUL_ENABLE_LIVE_SNMP_RUNTIME") != "1",
        reason="set TRISHUL_ENABLE_LIVE_SNMP_RUNTIME=1 to run live UDP runtime tests",
    ),
]


def _activate_runtime_bundle(isolated_db):
    from app.services.bundles import BundleCompileRequest, BundleService

    service = BundleService(isolated_db["settings"])
    result = service.compile_bundle(
        BundleCompileRequest(
            mib_names=["SNMPv2-MIB", "IF-MIB"],
            activate=True,
        )
    )
    return result["activation"]["bundle"]


def _pick_free_udp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_live_runtime_notification_listener_trap_and_inform(isolated_db):
    from app.services.runtime import RuntimeService

    active_bundle = _activate_runtime_bundle(isolated_db)
    listener_port = _pick_free_udp_port()

    async def scenario():
        service = RuntimeService(isolated_db["settings"])
        try:
            started = await service.start_listener(
                host="127.0.0.1",
                port=listener_port,
                communities=["public"],
            )
            assert started["active_bundle"]["id"] == active_bundle["id"]
            assert started["listener"]["running"] is True

            trap_result = await service.send_trap(
                host="127.0.0.1",
                port=listener_port,
                community="public",
                notification="IF-MIB::linkDown",
                uptime=321,
                varbinds=[
                    {
                        "target": "IF-MIB::ifIndex.1",
                        "value": {"type": "integer", "value": 1},
                    },
                    {
                        "target": "IF-MIB::ifAdminStatus.1",
                        "value": {"type": "integer", "value": 1},
                    },
                    {
                        "target": "IF-MIB::ifOperStatus.1",
                        "value": {"type": "integer", "value": 1},
                    },
                ],
            )
            assert trap_result["request_id"] > 0

            inform_result = await service.send_inform(
                host="127.0.0.1",
                port=listener_port,
                community="public",
                notification="IF-MIB::linkDown",
                uptime=654,
                varbinds=[
                    {
                        "target": "IF-MIB::ifIndex.2",
                        "value": {"type": "integer", "value": 2},
                    },
                    {
                        "target": "IF-MIB::ifAdminStatus.2",
                        "value": {"type": "integer", "value": 1},
                    },
                    {
                        "target": "IF-MIB::ifOperStatus.2",
                        "value": {"type": "integer", "value": 1},
                    },
                ],
            )
            assert inform_result["response"]["error_status"] == "no_error"

            for _ in range(40):
                events = await service.list_notification_events(limit=10)
                if events["total"] >= 2:
                    break
                await asyncio.sleep(0.05)
            else:
                raise AssertionError("listener did not capture both live notifications")

            items = events["items"]
            received = [item for item in items if item.get("direction") == "received"]
            assert len(received) >= 2
            assert all(item["notification_name"] == "IF-MIB::linkDown" for item in received[:2])
            assert {item["pdu_type"] for item in received[:2]} == {
                "snmpv2-trap",
                "inform-request",
            }
            assert any(
                binding["symbolic"] == "IF-MIB::ifIndex" and binding["varbind"] is not None
                for item in received[:2]
                for binding in item["member_bindings"]
            )
        finally:
            await service.shutdown()

    asyncio.run(scenario())
