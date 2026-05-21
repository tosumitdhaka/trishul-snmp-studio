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


def test_runtime_service_contracts_cover_responder_manager_and_notifications(
    isolated_db,
    monkeypatch,
):
    from app.services import runtime as runtime_module
    from trishul_snmp.mib import load_bundle
    from trishul_snmp.notify import NotificationEvent
    from trishul_snmp.types import (
        ErrorStatus,
        ObjectIdentifierValue,
        OctetStringValue,
        OidMatch,
        Response,
        TimeTicksValue,
        VarBind,
    )

    active_bundle = _activate_runtime_bundle(isolated_db)

    sys_name_varbind = VarBind(
        oid=(1, 3, 6, 1, 2, 1, 1, 5, 0),
        value=OctetStringValue(b"demo-agent"),
        match=OidMatch(
            oid=(1, 3, 6, 1, 2, 1, 1, 5, 0),
            module="SNMPv2-MIB",
            symbol="sysName",
            matched_oid=(1, 3, 6, 1, 2, 1, 1, 5),
            suffix=(0,),
            object_type="OBJECT-TYPE",
            nodetype="scalar",
        ),
        display_name="SNMPv2-MIB::sysName.0",
        display_value="demo-agent",
    )
    if_descr_varbind = VarBind(
        oid=(1, 3, 6, 1, 2, 1, 2, 2, 1, 2, 1),
        value=OctetStringValue(b"eth0"),
        match=OidMatch(
            oid=(1, 3, 6, 1, 2, 1, 2, 2, 1, 2, 1),
            module="IF-MIB",
            symbol="ifDescr",
            matched_oid=(1, 3, 6, 1, 2, 1, 2, 2, 1, 2),
            suffix=(1,),
            object_type="OBJECT-TYPE",
            nodetype="column",
        ),
        display_name="IF-MIB::ifDescr.1",
        display_value="eth0",
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
        request_id=101,
        error_status=ErrorStatus.NO_ERROR,
        error_index=0,
        varbinds=(sys_name_varbind,),
    )
    notification_event = NotificationEvent(
        request_id=202,
        community="public",
        source_address=("127.0.0.1", 50162),
        pdu_type="snmpv2-trap",
        varbinds=(uptime_varbind, trap_oid_varbind, if_descr_varbind),
        notification_oid=(1, 3, 6, 1, 6, 3, 1, 1, 5, 3),
        notification_name="IF-MIB::linkDown",
        notification_description="A linkDown test notification.",
        uptime=321,
    )

    class FakeResponder:
        instances: list["FakeResponder"] = []

        def __init__(
            self,
            *,
            host="0.0.0.0",
            port=161,
            communities=None,
            source=None,
            objects=(),
            bundle=None,
        ):
            self.host = host
            self.port = port
            self.communities = communities
            self.source = source
            self.bundle = bundle
            self.local_address = (host, port)
            self._objects = list(objects)
            self.closed = False
            self.clear_count = 0
            self.set_calls: list[tuple[tuple[str, object], ...]] = []
            FakeResponder.instances.append(self)

        async def open(self):
            return None

        async def close(self):
            self.closed = True

        async def serve_forever(self):
            while not self.closed:
                await asyncio.sleep(0)

        def set_objects(self, objects):
            payload = tuple(objects)
            self._objects.extend(payload)
            self.set_calls.append(payload)
            return tuple(range(len(payload)))

        def clear_objects(self):
            self.clear_count += 1
            self._objects.clear()

    class FakeManager:
        calls: list[tuple[str, tuple[str, ...], dict[str, object]]] = []

        def __init__(self, *, host, community, port=161, timeout=2.0, retries=1, bundle=None):
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

        async def get(self, *targets):
            FakeManager.calls.append(("get", targets, {"bundle": self.bundle}))
            return response

        async def get_next(self, *targets):
            FakeManager.calls.append(("get-next", targets, {"bundle": self.bundle}))
            return response

        async def get_bulk(self, *targets, non_repeaters=0, max_repetitions=10):
            FakeManager.calls.append(
                (
                    "get-bulk",
                    targets,
                    {
                        "bundle": self.bundle,
                        "non_repeaters": non_repeaters,
                        "max_repetitions": max_repetitions,
                    },
                )
            )
            return response

        async def walk(self, root, *, bulk=True, max_repetitions=10):
            FakeManager.calls.append(
                (
                    "walk",
                    (root,),
                    {"bundle": self.bundle, "bulk": bulk, "max_repetitions": max_repetitions},
                )
            )
            return (sys_name_varbind, if_descr_varbind)

        async def bulkwalk(self, root, *, max_repetitions=10):
            FakeManager.calls.append(
                (
                    "bulkwalk",
                    (root,),
                    {"bundle": self.bundle, "max_repetitions": max_repetitions},
                )
            )
            return (sys_name_varbind, if_descr_varbind)

    class FakeNotifier:
        calls: list[tuple[str, str, tuple[tuple[str, object], ...], int]] = []

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
            FakeNotifier.calls.append(("trap", notification, tuple(varbinds), uptime))
            return 77

        async def send_inform(self, notification, *, varbinds=(), uptime=0):
            FakeNotifier.calls.append(("inform", notification, tuple(varbinds), uptime))
            return response

    class FakeListener:
        instances: list["FakeListener"] = []

        def __init__(self, *, host="0.0.0.0", port=162, communities=None, bundle=None):
            self.host = host
            self.port = port
            self.communities = communities
            self.bundle = bundle
            self.local_address = (host, port)
            self.closed = False
            self.events = [notification_event]
            FakeListener.instances.append(self)

        async def open(self):
            return None

        async def close(self):
            self.closed = True

        def __aiter__(self):
            return self

        async def __anext__(self):
            while not self.closed:
                if self.events:
                    return self.events.pop(0)
                await asyncio.sleep(0)
            raise StopAsyncIteration

    monkeypatch.setattr(runtime_module, "V2cResponder", FakeResponder)
    monkeypatch.setattr(runtime_module, "V2cManager", FakeManager)
    monkeypatch.setattr(runtime_module, "V2cNotifier", FakeNotifier)
    monkeypatch.setattr(runtime_module, "V2cNotificationListener", FakeListener)
    bundle = load_bundle(active_bundle["storage_path"])

    async def scenario():
        service = runtime_module.RuntimeService(isolated_db["settings"])

        started = await service.start_responder(
            host="127.0.0.1",
            port=1161,
            communities=["public"],
            objects=[
                {
                    "target": "SNMPv2-MIB::sysName.0",
                    "value": {"type": "octet-string", "value": "demo-agent"},
                }
            ],
            rules=[
                {
                    "target": "IF-MIB::ifInOctets.1",
                    "kind": "counter",
                    "value_type": "counter32",
                    "start": 100,
                    "step": 5,
                },
                {
                    "target": "SNMPv2-MIB::sysUpTime.0",
                    "kind": "uptime",
                    "base": 321,
                },
            ],
        )
        assert started["active_bundle"]["id"] == active_bundle["id"]
        assert started["responder"]["running"] is True
        assert started["responder"]["bundle_set_id"] == active_bundle["id"]
        assert started["responder"]["configured_object_count"] == 1
        assert started["responder"]["configured_rule_count"] == 2
        assert str(FakeResponder.instances[-1].bundle.source) == active_bundle["storage_path"]
        assert FakeResponder.instances[-1].source is not None

        counter_oid = bundle.resolve("IF-MIB::ifInOctets.1")
        counter_value = FakeResponder.instances[-1].source.lookup_exact(counter_oid)
        next_counter_value = FakeResponder.instances[-1].source.lookup_exact(counter_oid)
        assert counter_value.value == 100
        assert next_counter_value.value == 105

        updated = await service.set_responder_objects(
            objects=[
                {
                    "target": "IF-MIB::ifDescr.1",
                    "value": {"type": "octet-string", "value": "eth0"},
                }
            ],
            replace=False,
        )
        assert updated["responder"]["configured_object_count"] == 2
        assert updated["responder"]["configured_rule_count"] == 2
        assert (
            FakeResponder.instances[-1]
            .source
            .lookup_exact(bundle.resolve("IF-MIB::ifDescr.1"))
            .value
            == b"eth0"
        )

        manager_get = await service.manager_get(
            host="127.0.0.1",
            port=1161,
            community="public",
            targets=["SNMPv2-MIB::sysName.0"],
        )
        assert manager_get["response"]["varbinds"][0]["symbolic"] == "SNMPv2-MIB::sysName.0"
        assert FakeManager.calls[-1][0] == "get"
        assert str(FakeManager.calls[-1][2]["bundle"].source) == active_bundle["storage_path"]

        manager_bulk = await service.manager_get_bulk(
            host="127.0.0.1",
            port=1161,
            community="public",
            targets=["IF-MIB::ifDescr.1"],
            non_repeaters=1,
            max_repetitions=5,
        )
        assert manager_bulk["response"]["error_status"] == "no_error"
        assert FakeManager.calls[-1][0] == "get-bulk"
        assert FakeManager.calls[-1][2]["max_repetitions"] == 5

        manager_walk = await service.manager_walk(
            host="127.0.0.1",
            port=1161,
            community="public",
            root="IF-MIB::ifDescr",
            bulk=True,
            max_repetitions=5,
        )
        assert manager_walk["operation"] == "bulkwalk"
        assert manager_walk["count"] == 2

        listener = await service.start_listener(
            host="127.0.0.1",
            port=1162,
            communities=["public"],
        )
        assert listener["listener"]["running"] is True
        await asyncio.sleep(0.01)

        events = await service.list_notification_events(limit=10)
        assert events["total"] == 1
        assert events["items"][0]["notification_name"] == "IF-MIB::linkDown"

        trap_result = await service.send_trap(
            host="127.0.0.1",
            port=1162,
            community="public",
            notification="IF-MIB::linkDown",
            uptime=321,
            varbinds=[
                {
                    "target": "IF-MIB::ifDescr.1",
                    "value": {"type": "octet-string", "value": "eth0"},
                }
            ],
        )
        assert trap_result["request_id"] == 77
        assert FakeNotifier.calls[-1][0] == "trap"

        inform_result = await service.send_inform(
            host="127.0.0.1",
            port=1162,
            community="public",
            notification="IF-MIB::linkDown",
            uptime=321,
        )
        assert inform_result["response"]["error_status"] == "no_error"
        assert FakeNotifier.calls[-1][0] == "inform"

        stopped_listener = await service.stop_listener()
        stopped_responder = await service.stop_responder()
        assert stopped_listener["listener"]["running"] is False
        assert stopped_responder["responder"]["running"] is False

        await service.shutdown()

    asyncio.run(scenario())


def test_runtime_transport_wrappers_cover_remaining_error_paths(
    isolated_db,
    monkeypatch,
):
    from app.services import runtime as runtime_module
    from app.services.history import EventHistoryServiceError
    from app.services.runtime import RuntimeBinding, RuntimeService, RuntimeServiceError

    active_bundle = _activate_runtime_bundle(isolated_db)
    service = RuntimeService(isolated_db["settings"])

    class BrokenResponder:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        async def open(self):
            raise ValueError("responder open failed")

    monkeypatch.setattr(runtime_module, "V2cResponder", BrokenResponder)
    with pytest.raises(RuntimeServiceError, match="responder open failed"):
        asyncio.run(
            service.start_responder(
                host="127.0.0.1",
                port=1161,
                communities=["public"],
                objects=[
                    {
                        "target": "SNMPv2-MIB::sysName.0",
                        "value": {"type": "octet-string", "value": "demo"},
                    }
                ],
            )
        )

    service._responder_binding = RuntimeBinding(
        host="127.0.0.1",
        port=1161,
        communities=("public",),
        bundle_set_id=active_bundle["id"] + 1,
    )
    with pytest.raises(RuntimeServiceError, match="older active bundle"):
        asyncio.run(
            service.set_responder_objects(
                objects=[
                    {
                        "target": "SNMPv2-MIB::sysName.0",
                        "value": {"type": "octet-string", "value": "updated"},
                    }
                ],
                replace=True,
            )
        )

    class BadResponder:
        def clear_objects(self):
            return None

        def set_objects(self, objects):
            del objects
            raise ValueError("set objects failed")

    service._responder_binding = RuntimeBinding(
        host="127.0.0.1",
        port=1161,
        communities=("public",),
        bundle_set_id=active_bundle["id"],
    )
    service._responder = BadResponder()
    service._responder_source = None
    with pytest.raises(RuntimeServiceError, match="set objects failed"):
        asyncio.run(
            service.set_responder_objects(
                objects=[
                    {
                        "target": "SNMPv2-MIB::sysDescr.0",
                        "value": {"type": "octet-string", "value": "suite"},
                    }
                ],
                replace=True,
            )
        )

    class StubManager:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            del exc_type, exc, tb

        async def walk(self, root, *, bulk=True, max_repetitions=10):
            del root, bulk, max_repetitions
            raise ValueError("walk failed")

        async def bulkwalk(self, root, *, max_repetitions=10):
            del root, max_repetitions
            return ()

    monkeypatch.setattr(runtime_module, "V2cManager", StubManager)
    with pytest.raises(RuntimeServiceError, match="walk failed"):
        asyncio.run(
            service.manager_walk(
                host="127.0.0.1",
                port=1161,
                community="public",
                root="1.3.6.1.2.1.1",
                bulk=False,
            )
        )

    with pytest.raises(
        RuntimeServiceError,
        match="Unsupported manager operation: unsupported",
    ):
        asyncio.run(
            service._run_manager_response(
                operation="unsupported",
                host="127.0.0.1",
                port=1161,
                community="public",
                timeout=2.0,
                retries=1,
                targets=["1.3.6.1.2.1.1.1.0"],
            )
        )

    class BrokenListener:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        async def open(self):
            raise ValueError("listener open failed")

    monkeypatch.setattr(runtime_module, "V2cNotificationListener", BrokenListener)
    with pytest.raises(RuntimeServiceError, match="listener open failed"):
        asyncio.run(
            service.start_listener(
                host="127.0.0.1",
                port=1162,
                communities=["public"],
            )
        )

    class BrokenNotifier:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            del exc_type, exc, tb

        async def send_trap(self, notification, *, varbinds=(), uptime=0):
            del notification, varbinds, uptime
            raise ValueError("trap failed")

        async def send_inform(self, notification, *, varbinds=(), uptime=0):
            del notification, varbinds, uptime
            raise ValueError("inform failed")

    monkeypatch.setattr(runtime_module, "V2cNotifier", BrokenNotifier)
    with pytest.raises(RuntimeServiceError, match="trap failed"):
        asyncio.run(
            service.send_trap(
                host="127.0.0.1",
                port=1162,
                community="public",
                notification="IF-MIB::linkDown",
            )
        )
    with pytest.raises(RuntimeServiceError, match="inform failed"):
        asyncio.run(
            service.send_inform(
                host="127.0.0.1",
                port=1162,
                community="public",
                notification="IF-MIB::linkUp",
            )
        )

    def raise_history_error(event_id):
        del event_id
        raise EventHistoryServiceError("history failed")

    service.history_service.get_event = raise_history_error
    with pytest.raises(RuntimeServiceError, match="history failed"):
        asyncio.run(service.replay_notification_event(event_id=1))

    service.history_service.get_event = lambda event_id: {"id": event_id, "event": "bad"}
    with pytest.raises(
        RuntimeServiceError,
        match="Stored notification event payload is unavailable.",
    ):
        asyncio.run(service.replay_notification_event(event_id=2))

    service.history_service.get_event = lambda event_id: {
        "id": event_id,
        "event": {
            "pdu_type": "snmpv2-trap",
            "community": "public",
            "target": {"host": "127.0.0.1", "port": 162},
            "uptime": "bad",
        },
    }
    with pytest.raises(
        RuntimeServiceError,
        match="Stored notification event has an invalid uptime value.",
    ):
        asyncio.run(service.replay_notification_event(event_id=3))

    def raise_decode_error(data, *, bundle, source_address):
        del data, bundle, source_address
        raise ValueError("decode failed")

    monkeypatch.setattr(runtime_module, "decode_notification", raise_decode_error)
    with pytest.raises(RuntimeServiceError, match="decode failed"):
        asyncio.run(
            service.decode_notification_payload(
                payload="4142",
                encoding="hex",
            )
        )
