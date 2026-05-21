from __future__ import annotations

import asyncio

import pytest

pytestmark = pytest.mark.unit


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


def test_runtime_persists_sent_events_and_replays_notification_history(
    isolated_db,
    monkeypatch,
):
    from app.services import runtime as runtime_module
    from app.services.history import EventHistoryService
    from trishul_snmp.notify import NotificationEvent
    from trishul_snmp.types import (
        ErrorStatus,
        IntegerValue,
        ObjectIdentifierValue,
        OidMatch,
        Response,
        TimeTicksValue,
        VarBind,
    )

    active_bundle = _activate_runtime_bundle(isolated_db)

    if_index_varbind = VarBind(
        oid=(1, 3, 6, 1, 2, 1, 2, 2, 1, 1, 1),
        value=IntegerValue(1),
        match=OidMatch(
            oid=(1, 3, 6, 1, 2, 1, 2, 2, 1, 1, 1),
            module="IF-MIB",
            symbol="ifIndex",
            matched_oid=(1, 3, 6, 1, 2, 1, 2, 2, 1, 1),
            suffix=(1,),
            object_type="OBJECT-TYPE",
            nodetype="column",
        ),
        display_name="IF-MIB::ifIndex.1",
        display_value="1",
    )
    trap_oid_varbind = VarBind(
        oid=(1, 3, 6, 1, 6, 3, 1, 1, 4, 1, 0),
        value=ObjectIdentifierValue((1, 3, 6, 1, 6, 3, 1, 1, 5, 3)),
        display_name="SNMPv2-MIB::snmpTrapOID.0",
        display_value="1.3.6.1.6.3.1.1.5.3",
    )
    uptime_varbind = VarBind(
        oid=(1, 3, 6, 1, 2, 1, 1, 3, 0),
        value=TimeTicksValue(321),
        display_name="SNMPv2-MIB::sysUpTime.0",
        display_value="321",
    )
    response = Response(
        request_id=303,
        error_status=ErrorStatus.NO_ERROR,
        error_index=0,
        varbinds=(),
    )

    class FakeNotifier:
        calls: list[dict[str, object]] = []

        def __init__(self, *, host, community, port=162, timeout=2.0, retries=1, bundle=None):
            self.host = host
            self.community = community
            self.port = port
            self.timeout = timeout
            self.retries = retries
            self.bundle = bundle

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            del exc_type, exc, tb

        async def send_trap(self, notification, *, varbinds=(), uptime=0):
            FakeNotifier.calls.append(
                {
                    "operation": "trap",
                    "host": self.host,
                    "port": self.port,
                    "community": self.community,
                    "timeout": self.timeout,
                    "retries": self.retries,
                    "notification": notification,
                    "varbinds": tuple(varbinds),
                    "uptime": uptime,
                }
            )
            return 77

        async def send_inform(self, notification, *, varbinds=(), uptime=0):
            FakeNotifier.calls.append(
                {
                    "operation": "inform",
                    "host": self.host,
                    "port": self.port,
                    "community": self.community,
                    "timeout": self.timeout,
                    "retries": self.retries,
                    "notification": notification,
                    "varbinds": tuple(varbinds),
                    "uptime": uptime,
                }
            )
            return response

    monkeypatch.setattr(runtime_module, "V2cNotifier", FakeNotifier)

    received_event = NotificationEvent(
        request_id=202,
        community="public",
        source_address=("192.0.2.44", 40162),
        pdu_type="snmpv2-trap",
        varbinds=(uptime_varbind, trap_oid_varbind, if_index_varbind),
        notification_oid=(1, 3, 6, 1, 6, 3, 1, 1, 5, 3),
        notification_name="IF-MIB::linkDown",
        notification_description="A linkDown test notification.",
        uptime=321,
    )

    async def scenario():
        runtime = runtime_module.RuntimeService(isolated_db["settings"])
        history = EventHistoryService(isolated_db["settings"])

        sent = await runtime.send_inform(
            host="198.51.100.8",
            port=20162,
            community="public",
            notification="IF-MIB::linkDown",
            timeout=1.5,
            retries=0,
            uptime=321,
            varbinds=[
                {
                    "target": "IF-MIB::ifIndex.1",
                    "value": {"type": "integer", "value": 1},
                }
            ],
        )
        assert sent["event"]["direction"] == "sent"
        assert sent["event"]["target_address"] == {"host": "198.51.100.8", "port": 20162}
        assert sent["event"]["target"]["retries"] == 0

        sent_history = history.list_events(direction="sent")
        assert sent_history["total"] == 1
        stored_sent = history.get_event(sent["event"]["event_id"])
        assert stored_sent["event"]["notification_name"] == "IF-MIB::linkDown"
        assert stored_sent["event"]["target"]["host"] == "198.51.100.8"
        assert stored_sent["event"]["target"]["retries"] == 0

        replayed_sent = await runtime.replay_notification_event(
            event_id=sent["event"]["event_id"]
        )
        assert replayed_sent["operation"] == "inform"
        assert replayed_sent["replayed_from_event_id"] == sent["event"]["event_id"]
        assert FakeNotifier.calls[-1]["operation"] == "inform"
        assert FakeNotifier.calls[-1]["host"] == "198.51.100.8"
        assert FakeNotifier.calls[-1]["retries"] == 0

        serialized_received = runtime._serialize_event(
            received_event,
            direction="received",
            received_at="2026-05-11T00:00:00+00:00",
        )
        stored_received = history.record_event(
            direction="received",
            pdu_type="snmpv2-trap",
            bundle_set_id=active_bundle["id"],
            request_id=received_event.request_id,
            community=received_event.community,
            source_host="192.0.2.44",
            source_port=40162,
            notification_oid=serialized_received["notification_oid"],
            notification_name=serialized_received["notification_name"],
            notification_description=serialized_received["notification_description"],
            uptime=serialized_received["uptime"],
            event=serialized_received,
        )

        replayed_received = await runtime.replay_notification_event(
            event_id=stored_received["event_id"],
            host="203.0.113.20",
            port=1162,
            community="lab",
        )
        assert replayed_received["operation"] == "trap"
        assert replayed_received["replayed_from_event_id"] == stored_received["event_id"]
        assert FakeNotifier.calls[-1]["operation"] == "trap"
        assert FakeNotifier.calls[-1]["host"] == "203.0.113.20"
        assert FakeNotifier.calls[-1]["community"] == "lab"
        assert [target for target, _value in FakeNotifier.calls[-1]["varbinds"]] == [
            "1.3.6.1.2.1.2.2.1.1.1",
        ]

        await runtime.shutdown()

    asyncio.run(scenario())


def test_runtime_decode_notification_uses_active_bundle_metadata(isolated_db):
    from app.services.runtime import RuntimeService
    from trishul_snmp.mib import load_bundle
    from trishul_snmp.notify.client import encode_notification_raw_varbinds
    from trishul_snmp.types import IntegerValue, OctetStringValue
    from trishul_snmp.wire.message import SnmpMessage, encode_message
    from trishul_snmp.wire.pdu import Pdu, PduType

    active_bundle = _activate_runtime_bundle(isolated_db)
    bundle = load_bundle(active_bundle["storage_path"])
    raw_varbinds = encode_notification_raw_varbinds(
        bundle.resolve("IF-MIB::linkDown"),
        varbinds=[
            ("IF-MIB::ifIndex.1", IntegerValue(1)),
            ("IF-MIB::ifDescr.1", OctetStringValue(b"eth0")),
        ],
        uptime=321,
        bundle=bundle,
    )
    payload = encode_message(
        SnmpMessage(
            version=1,
            community="public",
            pdu=Pdu(
                pdu_type=PduType.SNMPV2_TRAP,
                request_id=11,
                error_status=0,
                error_index=0,
                varbinds=raw_varbinds,
            ),
        )
    ).hex()

    async def scenario():
        service = RuntimeService(isolated_db["settings"])
        decoded = await service.decode_notification_payload(
            payload=payload,
            encoding="hex",
            source_host="127.0.0.1",
            source_port=1162,
        )
        event = decoded["event"]
        assert decoded["active_bundle"]["id"] == active_bundle["id"]
        assert event["notification_name"] == "IF-MIB::linkDown"
        assert event["uptime"] == 321
        assert event["source_address"] == {"host": "127.0.0.1", "port": 1162}
        assert any(varbind["symbolic"] == "IF-MIB::ifIndex.1" for varbind in event["varbinds"])
        assert any(
            binding["symbolic"] == "IF-MIB::ifIndex"
            for binding in event["member_bindings"]
        )

    asyncio.run(scenario())


def test_runtime_send_trap_records_numeric_notification_without_active_bundle(
    isolated_db,
    monkeypatch,
):
    from app.services import runtime as runtime_module
    from app.services.history import EventHistoryService

    class FakeNotifier:
        calls: list[dict[str, object]] = []

        def __init__(self, *, host, community, port=162, timeout=2.0, retries=1, bundle=None):
            self.host = host
            self.community = community
            self.port = port
            self.timeout = timeout
            self.retries = retries
            self.bundle = bundle

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            del exc_type, exc, tb

        async def send_trap(self, notification, *, varbinds=(), uptime=0):
            FakeNotifier.calls.append(
                {
                    "host": self.host,
                    "port": self.port,
                    "community": self.community,
                    "notification": notification,
                    "varbinds": tuple(varbinds),
                    "uptime": uptime,
                    "bundle": self.bundle,
                }
            )
            return 55

    monkeypatch.setattr(runtime_module, "V2cNotifier", FakeNotifier)

    async def scenario():
        runtime = runtime_module.RuntimeService(isolated_db["settings"])
        history = EventHistoryService(isolated_db["settings"])

        sent = await runtime.send_trap(
            host="127.0.0.1",
            port=1162,
            community="public",
            notification="1.3.6.1.6.3.1.1.5.1",
            varbinds=[
                {
                    "target": "1.3.6.1.2.1.1.5.0",
                    "value": {"type": "octet-string", "value": "lab-agent"},
                }
            ],
        )

        assert sent["active_bundle"] is None
        assert sent["request_id"] == 55
        assert FakeNotifier.calls[-1]["bundle"] is None
        assert sent["event"]["notification_oid"] == "1.3.6.1.6.3.1.1.5.1"
        assert sent["event"]["notification_name"] == "1.3.6.1.6.3.1.1.5.1"
        assert sent["event"]["varbinds"][0]["oid"] == "1.3.6.1.2.1.1.5.0"
        assert sent["event"]["varbinds"][0]["match"] is None
        assert sent["event"]["varbinds"][0]["display_value"] == "lab-agent"

        sent_history = history.list_events(direction="sent")
        assert sent_history["total"] == 1
        stored_event = history.get_event(sent["event"]["event_id"])
        assert stored_event["event"]["notification_name"] == "1.3.6.1.6.3.1.1.5.1"

        await runtime.shutdown()

    asyncio.run(scenario())


def test_runtime_send_trap_uses_latest_compiled_bundle_when_none_is_marked_active(
    isolated_db,
    monkeypatch,
):
    from app.services import runtime as runtime_module
    from app.services.bundles import BundleCompileRequest, BundleService

    class FakeNotifier:
        calls: list[dict[str, object]] = []

        def __init__(self, *, host, community, port=162, timeout=2.0, retries=1, bundle=None):
            self.host = host
            self.community = community
            self.port = port
            self.timeout = timeout
            self.retries = retries
            self.bundle = bundle

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            del exc_type, exc, tb

        async def send_trap(self, notification, *, varbinds=(), uptime=0):
            FakeNotifier.calls.append(
                {
                    "notification": notification,
                    "varbinds": tuple(varbinds),
                    "bundle": self.bundle,
                    "uptime": uptime,
                }
            )
            return 88

    monkeypatch.setattr(runtime_module, "V2cNotifier", FakeNotifier)

    bundle_service = BundleService(isolated_db["settings"])
    compiled = bundle_service.compile_bundle(BundleCompileRequest(mib_names=["IF-MIB"]))

    async def scenario():
        runtime = runtime_module.RuntimeService(isolated_db["settings"])
        sent = await runtime.send_trap(
            host="127.0.0.1",
            port=1162,
            community="public",
            notification="IF-MIB::linkDown",
        )

        assert sent["request_id"] == 88
        assert sent["active_bundle"]["id"] == compiled["bundle"]["id"]
        assert FakeNotifier.calls[-1]["bundle"] is not None
        assert FakeNotifier.calls[-1]["notification"] == "IF-MIB::linkDown"

        await runtime.shutdown()

    asyncio.run(scenario())
