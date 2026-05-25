"""SNMP walk execution and result formatting service."""
from __future__ import annotations

import re
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any

from app.core.config import Settings
from app.core.logging import emit_backend_log
from app.services.state_store import (
    StateStore,
    _WALK_OIDS_RETURNED_KEY,
    _WALKS_EXECUTED_KEY,
)
from app.services.realtime import broadcast_stats


class WalkerError(RuntimeError):
    pass


def _extract_value(entry: dict[str, Any]) -> Any:
    v = entry.get("value")
    if isinstance(v, dict):
        if "value" in v:
            return v.get("value")
        if "display" in v:
            return v.get("display")
    return entry.get("display_value")


def _walk_item(entry: dict[str, Any], *, use_mibs: bool) -> dict[str, Any]:
    value = _extract_value(entry)
    if use_mibs:
        return {
            "oid": entry["oid"],
            "symbolic": entry.get("symbolic") or entry["oid"],
            "type": entry.get("value_type"),
            "value": value,
        }
    return {"oid": entry["oid"], "type": entry.get("value_type"), "value": value}


def _walk_line(entry: dict[str, Any], *, use_mibs: bool) -> str:
    label = (entry.get("symbolic") or entry["oid"]) if use_mibs else entry["oid"]
    return f"{label} = {_extract_value(entry)}"


def _value_is_metric(object_name: str, value_type: str, value: Any) -> bool:
    del value
    if value_type not in {"integer", "counter32", "counter64", "gauge32", "timeticks"}:
        return False
    low = str(object_name or "").strip().lower()
    return not any(t in low for t in (
        "index", "id", "name", "descr", "serial", "mac", "type", "version",
        "status", "address", "phys",
    ))


def _metric_value(value_type: str, value: Any) -> int | float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        numeric = float(value)
    else:
        text = str(value).strip()
        if not text:
            return None
        m = re.search(r"(-?\d+)", text)
        if m is None:
            return None
        numeric = float(m.group(1))
    if value_type == "timeticks":
        numeric /= 100.0
    return int(numeric) if float(numeric).is_integer() else numeric


def _walk_compat_items(
    varbinds: list[dict[str, Any]],
    *,
    target_host: str,
    root_oid: str,
    use_mibs: bool,
) -> list[dict[str, Any]]:
    category = root_oid.split("::", 1)[1] if "::" in root_oid else root_oid
    timestamp = int(datetime.now(timezone.utc).timestamp())
    rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for entry in varbinds:
        symbolic = str(entry.get("symbolic") or "").strip()
        oid = str(entry.get("oid") or "").strip()
        label = symbolic if use_mibs and symbolic else oid
        if not label:
            continue
        module_name, object_name, index = "Unknown", label, "0"
        remainder = label
        if "::" in label:
            module_name, remainder = label.split("::", 1)
            module_name = module_name.strip() or "Unknown"
            remainder = remainder.strip()
        if "." in remainder:
            object_name, index = remainder.split(".", 1)
        elif oid:
            parts = [p for p in oid.split(".") if p]
            if len(parts) > 1:
                object_name = remainder or oid
                index = parts[-1]
        object_name = object_name.strip() or remainder or oid
        index = index.strip() or "0"
        value = _extract_value(entry)
        value_type = str(entry.get("value_type") or "").strip().lower()
        row = rows.setdefault(index, {"index": index, "labels": {}, "metrics": {}})
        if _value_is_metric(object_name, value_type, value):
            mv = _metric_value(value_type, value)
            if mv is None:
                row["labels"][object_name] = value
            else:
                row["metrics"][object_name] = {"value": mv, "module": module_name}
        else:
            row["labels"][object_name] = value
    output = []
    for row in rows.values():
        labels = dict(row["labels"])
        labels["snmp_index"] = row["index"]
        for metric_name, md in row["metrics"].items():
            output.append({
                "metric_name": metric_name,
                "value": md["value"],
                "mib_module": md["module"],
                "metric_category": category,
                "agent_host": target_host,
                "timestamp": timestamp,
                "labels": labels.copy(),
            })
    return output


async def execute(
    *,
    target: str,
    port: int,
    community: str,
    oid: str,
    parse: bool,
    use_mibs: bool,
    json_format: str = "current",
    settings: Settings,
    state: StateStore,
    runtime_service,
) -> dict[str, Any]:
    from app.services.runtime import RuntimeServiceError
    raw_format = str(json_format or "flat").strip().lower()
    if raw_format in {"grouped", "metrics"}:
        normalized_format = "grouped"
    else:
        normalized_format = "flat"
    try:
        result = await runtime_service.manager_walk(
            host=target, port=port, community=community, root=oid, bulk=True
        )
    except RuntimeServiceError as exc:
        emit_backend_log(
            f"Walk failed for {target}:{port} root={oid}: {exc}",
            level="ERROR", logger_name="app.operations", settings=settings,
        )
        raise WalkerError(str(exc)) from exc

    varbinds = result.get("varbinds", [])
    state.increment_counter(_WALKS_EXECUTED_KEY, 1)
    state.increment_counter(_WALK_OIDS_RETURNED_KEY, len(varbinds))
    raw_lines = [_walk_line(e, use_mibs=use_mibs) for e in varbinds]
    emit_backend_log(
        f"Walk completed for {target}:{port} root={oid} count={len(varbinds)} "
        f"parse={bool(parse)} use_mibs={bool(use_mibs)} json_format={normalized_format}",
        logger_name="app.operations", settings=settings,
    )
    await broadcast_stats(settings=settings)

    if parse:
        if normalized_format == "grouped":
            items = _walk_compat_items(varbinds, target_host=target, root_oid=oid, use_mibs=use_mibs)
            if not items and raw_lines:
                return {"mode": "label", "count": len(raw_lines), "data": raw_lines, "rawLines": raw_lines, "json_format": normalized_format}
        else:
            items = [_walk_item(e, use_mibs=use_mibs) for e in varbinds]
        return {"mode": "parsed", "count": len(items), "data": items, "rawLines": raw_lines, "json_format": normalized_format}

    return {"mode": "raw", "count": len(raw_lines), "data": raw_lines, "rawLines": raw_lines, "json_format": normalized_format}
