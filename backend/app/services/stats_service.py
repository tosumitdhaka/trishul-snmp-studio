"""Stats aggregation service."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.services.state_store import (
    StateStore,
    _MIB_RELOAD_COUNT_KEY,
    _STATS_RESET_AT_KEY,
    _WALK_OIDS_RETURNED_KEY,
    _WALKS_EXECUTED_KEY,
)

_MIB_SOURCE_EXTENSIONS = {".mib", ".txt", ".my"}


def _count_uploaded_sources(upload_root: Path) -> int:
    if not upload_root.exists():
        return 0
    return sum(
        1 for path in upload_root.rglob("*")
        if path.is_file() and path.suffix.lower() in _MIB_SOURCE_EXTENSIONS
    )


async def get_stats(
    *,
    state: StateStore,
    history_service,
    runtime_service,
    settings=None,
) -> dict[str, Any]:
    runtime_state = await runtime_service.get_state()
    responder = runtime_state.get("responder") or {}
    received_total = int(history_service.list_events(direction="received", limit=1, offset=0)["total"])
    sent_total = int(history_service.list_events(direction="sent", limit=1, offset=0)["total"])
    configured_object_count = responder.get("configured_object_count")
    runtime_settings = settings or getattr(history_service, "settings", None) or get_settings()
    upload_count = _count_uploaded_sources(runtime_settings.data_dir / "mibs")

    from app.services.bundle_state import get_bundle
    bundle = get_bundle()
    if configured_object_count is not None:
        oids_loaded = int(configured_object_count)
    elif bundle is not None:
        # Count objects from the active bundle as a baseline
        oids_loaded = sum(len(m.objects) for m in bundle.modules.values())
    else:
        oids_loaded = 0

    return {
        "simulator": {
            "snmp_requests_served": int(responder.get("request_count") or 0),
            "oids_loaded": oids_loaded,
        },
        "traps": {
            "traps_received_total": received_total,
            "traps_sent_total": sent_total,
        },
        "walker": {
            "walks_executed": state.counter(_WALKS_EXECUTED_KEY),
            "oids_returned": state.counter(_WALK_OIDS_RETURNED_KEY),
        },
        "mibs": {
            "upload_count": upload_count,
            "reload_count": state.counter(_MIB_RELOAD_COUNT_KEY),
        },
    }


async def reset_stats(
    *,
    state: StateStore,
    history_service=None,
    runtime_service=None,
) -> dict[str, str]:
    state.set_value(_STATS_RESET_AT_KEY, datetime.now(timezone.utc).isoformat())
    state.set_value(_WALKS_EXECUTED_KEY, 0)
    state.set_value(_WALK_OIDS_RETURNED_KEY, 0)
    state.set_value(_MIB_RELOAD_COUNT_KEY, 0)
    if history_service is not None and hasattr(history_service, "clear_events"):
        history_service.clear_events()
    if runtime_service is not None and hasattr(runtime_service, "reset_responder_counters"):
        await runtime_service.reset_responder_counters()
    return {"status": "reset"}
