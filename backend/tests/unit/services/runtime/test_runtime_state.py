from __future__ import annotations

import asyncio
import time

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


def test_runtime_rule_providers_and_binding_helpers_cover_core_state(isolated_db):
    from app.services.runtime import (
        RuntimeBinding,
        RuntimeObjectSpec,
        RuntimeRuleSpec,
        RuntimeService,
        _TimestampStringRule,
    )
    from trishul_snmp import CounterRule, InMemoryObjectSource, RandomNumericRule, UptimeRule
    from trishul_snmp.types import Counter32Value, IntegerValue, TimeTicksValue

    service = RuntimeService(isolated_db["settings"])

    counter_rule = CounterRule(start=5, increment=2, value_type=Counter32Value)
    assert service._serialize_value(counter_rule.get_value())["value"] == 5
    assert service._serialize_value(counter_rule.get_value())["value"] == 7

    random_rule = RandomNumericRule(min=3, max=3, value_type=IntegerValue)
    assert service._serialize_value(random_rule.get_value())["value"] == 3

    ts_rule = _TimestampStringRule(format_name="unix")
    assert service._serialize_value(ts_rule.get_value())["type"] == "octet-string"

    uptime_rule = UptimeRule()
    time.sleep(0.05)
    assert service._serialize_value(uptime_rule.get_value())["value"] >= 0

    static_object = RuntimeObjectSpec(
        target="1.3.6.1.2.1.1.5.0",
        oid=(1, 3, 6, 1, 2, 1, 1, 5, 0),
        value=IntegerValue(11),
    )
    counter_rule_spec = RuntimeRuleSpec(
        target="1.3.6.1.2.1.1.3.0",
        oid=(1, 3, 6, 1, 2, 1, 1, 3, 0),
        kind="counter",
        definition={"kind": "counter"},
        rule=CounterRule(start=20, increment=1, value_type=TimeTicksValue),
    )

    source = InMemoryObjectSource()
    source.set_object(static_object.oid, static_object.value)
    source.set_object(counter_rule_spec.oid, counter_rule_spec.rule)
    assert service._serialize_value(source.lookup_exact(static_object.oid))["value"] == 11
    assert service._serialize_value(source.lookup_exact(counter_rule_spec.oid))["value"] == 20
    assert source.lookup_next((1, 3, 6, 1, 2, 1, 1, 4, 0))[0] == static_object.oid
    assert source.lookup_next(static_object.oid) is None

    source.set_object((1, 3, 6, 1, 2, 1, 1, 6, 0), IntegerValue(13))
    assert service._runtime_object_inputs([static_object]) == (
        ("1.3.6.1.2.1.1.5.0", static_object.value),
    )

    active_bundle = {"id": 9}
    binding = RuntimeBinding(
        host="127.0.0.1",
        port=1161,
        communities=("public",),
        bundle_set_id=9,
    )
    serialized = service._serialize_binding_state(
        binding=binding,
        running=True,
        local_address=("127.0.0.1", 1161),
        last_error=None,
        configured_objects=[{"target": "1.3.6.1.2.1.1.5.0"}],
        configured_rules=[{"target": "1.3.6.1.2.1.1.3.0"}],
        active_bundle=active_bundle,
    )
    assert serialized["stale_bundle"] is False
    assert serialized["local_address"] == {"host": "127.0.0.1", "port": 1161}
    assert serialized["configured_object_count"] == 1
    assert serialized["configured_rule_count"] == 1


def test_runtime_helper_branches_cover_singletons_serializers_and_oid_edges(
    isolated_db,
    monkeypatch,
):
    from app.services.runtime import (
        RuntimeService,
        RuntimeServiceError,
        _TimestampStringRule,
        _value_type_class,
        get_runtime_service,
        reset_runtime_service,
        shutdown_runtime_service,
    )
    from trishul_snmp import InMemoryObjectSource, TimestampRule
    from trishul_snmp.errors import UnknownOidError
    from trishul_snmp.mib import load_bundle
    from trishul_snmp.types import Counter64Value, Gauge32Value, IpAddressValue, NullValue, ObjectIdentifierValue

    blank_service = RuntimeService(isolated_db["settings"])
    assert blank_service._get_active_bundle_identity() is None

    active_bundle = _activate_runtime_bundle(isolated_db)
    bundle = load_bundle(active_bundle["storage_path"])
    service = RuntimeService(isolated_db["settings"])

    class UnknownValue:
        type_name = "unknown"

        def to_display_string(self):
            return "unknown"

    iso_timestamp = _TimestampStringRule(format_name="iso8601").get_value()
    assert service._serialize_value(iso_timestamp)["value"].startswith("20")
    assert service._serialize_value(
        TimestampRule(value_type=Counter64Value).get_value()
    )["type"] == "counter64"

    source = InMemoryObjectSource()
    assert source.lookup_next((1, 3, 6, 1, 2, 1, 1, 8, 0)) is None

    assert isinstance(_value_type_class("gauge32")(1), Gauge32Value)
    assert isinstance(_value_type_class("counter64")(1), Counter64Value)
    with pytest.raises(KeyError):
        _value_type_class("octet-string")

    assert service._normalize_numeric_rule_value_type(None, default="integer") == "integer"
    with pytest.raises(RuntimeServiceError, match="rule value_type must be a non-empty string"):
        service._normalize_numeric_rule_value_type(" ", default="integer")
    assert service._normalize_timestamp_rule_value_type(None) == "octet-string"
    with pytest.raises(
        RuntimeServiceError,
        match="timestamp rule value_type must be a non-empty string",
    ):
        service._normalize_timestamp_rule_value_type(" ")
    assert service._normalize_timestamp_rule_format(None, default="unix") == "unix"
    with pytest.raises(
        RuntimeServiceError,
        match="timestamp rule format must be a non-empty string",
    ):
        service._normalize_timestamp_rule_format(" ", default="unix")

    assert service._serialize_value(ObjectIdentifierValue((1, 3, 6, 1)))["value"] == "1.3.6.1"
    assert service._serialize_value(IpAddressValue("127.0.0.1"))["value"] == "127.0.0.1"
    assert service._serialize_value(NullValue())["value"] is None
    assert service._serialize_value(UnknownValue())["value"] is None

    def raise_unknown_oid(oid):
        del oid
        raise UnknownOidError("missing")

    monkeypatch.setattr(bundle, "lookup", raise_unknown_oid)
    recorded = asyncio.run(
        service._record_sent_event(
            operation="trap",
            bundle=bundle,
            active_bundle=active_bundle,
            host="127.0.0.1",
            port=1162,
            community="public",
            timeout=2.0,
            retries=1,
            notification="1.3.6.1.4.1.99999.1",
            uptime=0,
            parsed_varbinds=[],
            request_id=91,
        )
    )
    assert recorded["notification_name"] == "1.3.6.1.4.1.99999.1"

    assert service._replay_varbind_inputs({"varbinds": None}) == []
    with pytest.raises(
        RuntimeServiceError,
        match="Stored notification event has an invalid varbind payload.",
    ):
        service._replay_varbind_inputs({"varbinds": [1]})
    with pytest.raises(
        RuntimeServiceError,
        match="Stored notification event is missing a varbind target.",
    ):
        service._replay_varbind_inputs(
            {"varbinds": [{"value": {"type": "integer", "value": 1}}]}
        )

    assert service._normalize_communities([]) is None
    with pytest.raises(
        RuntimeServiceError,
        match="value must contain a non-empty object identifier",
    ):
        service._coerce_oid(" ", bundle=None)
    with pytest.raises(RuntimeServiceError):
        service._coerce_oid("IF-MIB::missingSymbol.1", bundle=bundle)
    with pytest.raises(
        RuntimeServiceError,
        match="Object identifier arrays must contain integers",
    ):
        service._coerce_oid([1, "bad"], bundle=None)
    assert service._oid_to_str(None) is None

    reset_runtime_service()
    singleton_one = get_runtime_service(isolated_db["settings"])
    singleton_two = get_runtime_service(isolated_db["settings"])
    assert singleton_one is singleton_two
    asyncio.run(shutdown_runtime_service())
    reset_runtime_service()


def test_runtime_simulator_activity_log_tracks_requests_runtime_logs_and_clear(
    isolated_db,
    monkeypatch,
):
    from app.services.runtime import RuntimeService
    from trishul_snmp.types import IntegerValue, NullValue
    from trishul_snmp.wire.message import SnmpMessage
    from trishul_snmp.wire.pdu import Pdu, PduType, RawVarBind

    service = RuntimeService(isolated_db["settings"])
    runtime_logs: list[tuple[str, str]] = []
    monkeypatch.setattr(
        service,
        "_emit_runtime_log",
        lambda message, *, level="INFO": runtime_logs.append((level, message)),
    )
    request = SnmpMessage(
        version=1,
        community="public",
        pdu=Pdu(
            pdu_type=PduType.GET_NEXT,
            request_id=11,
            error_status=0,
            error_index=0,
            varbinds=(RawVarBind(oid=(1, 3, 6, 1, 2, 1, 1), value=NullValue()),),
        ),
    )
    response = SnmpMessage(
        version=1,
        community="public",
        pdu=Pdu(
            pdu_type=PduType.RESPONSE,
            request_id=11,
            error_status=0,
            error_index=0,
            varbinds=(RawVarBind(oid=(1, 3, 6, 1, 2, 1, 1, 1, 0), value=IntegerValue(7)),),
        ),
    )

    service._record_responder_request(request, response)
    activity = asyncio.run(service.list_simulator_activity(limit=10))
    assert activity["total"] == 1
    assert activity["items"][0]["request_type"] == "GETNEXT"
    assert activity["items"][0]["message"] == (
        "Simulator GETNEXT simulated 1 OID from 1.3.6.1.2.1.1 -> 1.3.6.1.2.1.1.1.0"
    )
    assert activity["items"][0]["first_requested_oid"] == "1.3.6.1.2.1.1"
    assert activity["items"][0]["first_returned_oid"] == "1.3.6.1.2.1.1.1.0"
    assert runtime_logs == [
        (
            "INFO",
            "Simulator GETNEXT simulated 1 OID from 1.3.6.1.2.1.1 -> 1.3.6.1.2.1.1.1.0",
        )
    ]

    cleared = asyncio.run(service.clear_simulator_activity())
    assert cleared["status"] == "cleared"
    assert asyncio.run(service.list_simulator_activity(limit=10))["items"] == []
