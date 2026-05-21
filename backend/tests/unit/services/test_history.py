from __future__ import annotations

from datetime import datetime, timezone

import pytest

pytestmark = pytest.mark.unit


def test_record_event_validates_inputs_and_persists_normalized_payloads(isolated_db):
    from app.services.history import EventHistoryService, EventHistoryServiceError

    service = EventHistoryService(isolated_db["settings"])

    with pytest.raises(EventHistoryServiceError, match="direction must be one of"):
        service.record_event(direction="bad", pdu_type="trap", event={})

    with pytest.raises(EventHistoryServiceError, match="pdu_type cannot be empty"):
        service.record_event(direction="received", pdu_type=" ", event={})

    with pytest.raises(EventHistoryServiceError, match="event must be a JSON object"):
        service.record_event(direction="received", pdu_type="trap", event=["bad"])

    with pytest.raises(EventHistoryServiceError, match="payload_hex must be a string"):
        service.record_event(direction="received", pdu_type="trap", event={}, payload_hex=123)

    payload = service.record_event(
        direction=" Received ",
        pdu_type=" snmpv2-trap ",
        event={"varbinds": [{"oid": "1.3.6.1.2.1.1.3.0"}]},
        bundle_set_id=7,
        community="public",
        source_host="127.0.0.1",
        source_port=2162,
        notification_oid="1.3.6.1.6.3.1.1.5.3",
        notification_name="IF-MIB::linkDown",
        notification_description="Interface down",
        payload_hex="beef",
    )

    assert payload["event_id"] >= 1
    assert payload["direction"] == "received"
    assert payload["source_address"] == {"host": "127.0.0.1", "port": 2162}
    assert payload["recorded_at"] is not None

    detailed = service.get_event(payload["event_id"])
    assert detailed["pdu_type"] == "snmpv2-trap"
    assert detailed["bundle_set_id"] == 7
    assert detailed["notification_name"] == "IF-MIB::linkDown"
    assert detailed["payload_available"] is True
    assert detailed["varbind_count"] == 1


def test_list_get_and_clear_events_cover_filters_search_and_paging(isolated_db):
    from app.services.history import EventHistoryService, EventHistoryServiceError

    service = EventHistoryService(isolated_db["settings"])
    first_time = datetime(2026, 5, 13, 6, 0, tzinfo=timezone.utc)
    second_time = datetime(2026, 5, 13, 7, 0, tzinfo=timezone.utc)

    first = service.record_event(
        direction="received",
        pdu_type="trap",
        event={"varbinds": [], "note": "uplink down"},
        bundle_set_id=1,
        community="public",
        source_host="router-a",
        source_port=2162,
        notification_oid="1.3.6.1.6.3.1.1.5.3",
        notification_name="IF-MIB::linkDown",
        recorded_at=first_time,
    )
    second = service.record_event(
        direction="sent",
        pdu_type="inform",
        event={"varbinds": [], "note": "auth failure"},
        bundle_set_id=2,
        community="private",
        target_host="collector-a",
        target_port=2162,
        notification_oid="1.3.6.1.6.3.1.1.5.5",
        notification_name="SNMPv2-MIB::authenticationFailure",
        payload_hex="cafe",
        recorded_at=second_time,
    )

    filtered = service.list_events(
        direction="received",
        source_host="router-a",
        notification="linkdown",
        bundle_set_id=1,
        recorded_from=first_time,
        recorded_to=first_time,
        limit=10,
    )
    assert filtered["total"] == 1
    assert filtered["items"][0]["id"] == first["event_id"]

    queried = service.list_events(q="auth", limit=10)
    assert queried["total"] == 1
    assert queried["items"][0]["id"] == second["event_id"]

    paged = service.list_events(limit=1, offset=1)
    assert paged["total"] == 2
    assert len(paged["items"]) == 1

    detailed = service.get_event(second["event_id"])
    assert detailed["id"] == second["event_id"]
    assert detailed["payload_hex"] == "cafe"
    assert detailed["event"]["event_id"] == second["event_id"]
    assert detailed["event"]["target_address"] == {"host": "collector-a", "port": 2162}

    with pytest.raises(EventHistoryServiceError, match="direction must be one of"):
        service.list_events(direction="bad")

    with pytest.raises(EventHistoryServiceError, match="limit must be between 1 and 500"):
        service.list_events(limit=0)

    with pytest.raises(EventHistoryServiceError, match="offset cannot be negative"):
        service.list_events(offset=-1)

    cleared = service.clear_events()
    assert cleared == {"status": "cleared", "deleted": 2}

    with pytest.raises(EventHistoryServiceError, match="does not exist"):
        service.get_event(first["event_id"])
