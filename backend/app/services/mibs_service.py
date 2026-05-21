"""MIB upload, reload, delete, status, export — flat service."""
from __future__ import annotations

from collections import OrderedDict
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.core.logging import emit_backend_log
from app.services.bundle_state import get_bundle
from app.services.state_store import (
    StateStore,
    _MIB_AUTO_FETCH_KEY,
    _MIB_RELOAD_COUNT_KEY,
    _MIB_REMOTE_SOURCES_KEY,
)


class MibsError(RuntimeError):
    pass


# Module-level source service singleton — caches disk scan results across requests.
# Invalidated (set to None) whenever the upload directory changes.
_source_svc_instance = None


def _invalidate_source_cache() -> None:
    global _source_svc_instance
    _source_svc_instance = None


def _log(message: str, settings: Settings, *, level: str = "INFO") -> None:
    emit_backend_log(message, level=level, logger_name="app.operations", settings=settings)


def _make_source_service(settings: Settings, state: StateStore, bundle_service):
    global _source_svc_instance
    if _source_svc_instance is not None:
        return _source_svc_instance

    from app.services.mib_sources import ShellMibSourceService

    _source_svc_instance = ShellMibSourceService(
        error_cls=MibsError,
        session_factory=bundle_service.session_factory,
        upload_dir=lambda: settings.data_dir / "mibs",
        bundled_mibs_dir=lambda: settings.bundled_mibs_dir,
        tsmi_cache_dir=lambda: settings.tsmi_cache_dir,
        load_settings=state.snapshot,
        emit_operation_log=lambda msg, level="INFO": _log(msg, settings, level=level),
        active_bundle_summary=bundle_service.get_effective_bundle_summary,
        unique_mib_names=bundle_service._unique_mib_names,
        bundled_mib_names=bundle_service.bundled_mib_names,
        mib_auto_fetch_key=_MIB_AUTO_FETCH_KEY,
        mib_remote_sources_key=_MIB_REMOTE_SOURCES_KEY,
    )
    return _source_svc_instance


def _make_mutation_service(settings: Settings, state: StateStore, bundle_service, source_svc):
    from app.services.mib_mutations import ShellMibMutationService

    return ShellMibMutationService(
        error_cls=MibsError,
        bundle_service=bundle_service,
        session_factory=bundle_service.session_factory,
        upload_dir=lambda: settings.data_dir / "mibs",
        bundled_mibs_dir=lambda: settings.bundled_mibs_dir,
        emit_operation_log=lambda msg, level="INFO": _log(msg, settings, level=level),
        increment_counter=lambda key, amount=1: state.increment_counter(key, amount),
        load_mib_status=lambda: get_status(settings=settings, state=state, bundle_service=bundle_service, source_svc=source_svc),
        analyze_upload_batch=source_svc.analyze_upload_batch,
        apply_upload_batch_policy=source_svc.apply_upload_batch_policy,
        remote_fetch_policy=source_svc.remote_fetch_policy,
        select_upload_targets=source_svc.select_upload_targets,
        normalize_source_group=source_svc.normalize_source_group,
        reset_source_caches=source_svc.reset_source_caches,
        compile_target_mib_names=source_svc.compile_target_mib_names,
        compile_source_dirs=source_svc.compile_source_dirs,
        uploaded_bundle_label=source_svc.uploaded_bundle_label,
        materialize_cached_remote_modules=source_svc.materialize_cached_remote_modules,
        upload_result_rows=source_svc.upload_result_rows,
        dependency_fetch_payload=source_svc.dependency_fetch_payload,
        missing_dependencies_from_error=source_svc.missing_dependencies_from_error,
        uploaded_mib_names=source_svc.uploaded_mib_names,
        reload_uploaded_mibs=lambda: reload(settings=settings, state=state, bundle_service=bundle_service),
        uploaded_target_path=source_svc.uploaded_target_path,
        relative_upload_path=source_svc.relative_upload_path,
        prune_empty_upload_dirs=source_svc.prune_empty_upload_dirs,
        active_source_map=source_svc.active_source_map,
        promoted_active_sources=source_svc.promoted_active_sources,
        available_source_mib_names=source_svc.available_source_mib_names,
        mib_reload_count_key=_MIB_RELOAD_COUNT_KEY,
    )


def get_status(
    *, settings: Settings, state: StateStore, bundle_service, source_svc=None
) -> dict[str, Any]:
    if source_svc is None:
        source_svc = _make_source_service(settings, state, bundle_service)

    from app.services.mib_sources import (
        BASE_IMPORT_MODULES,
        MANAGED_UPLOAD_SOURCE_KINDS,
    )

    def _imports_for_source(source_path: Path | None) -> list[str]:
        if source_path is None or not source_path.exists():
            return []
        try:
            text = source_path.read_text(errors="ignore")
        except OSError:
            return []
        return source_svc.extract_imported_modules(text)

    bundle = get_bundle()
    rows_by_module: dict[str, dict[str, Any]] = {}
    active_uploaded_paths: set[str] = set()
    active_uploaded_sources_by_module: dict[str, dict[str, Any]] = {}
    if bundle is not None:
        for mod_name, mod_record in bundle.modules.items():
            source_path = source_svc.source_path_for_module(mod_name)
            if source_path is not None and source_path.exists():
                source_kind = source_svc.module_source_kind(source_path)
                source_group = source_svc.source_group_for_path(source_path, source_kind=source_kind)
                relative_path = source_svc.source_relative_path(source_path, source_kind=source_kind)
                deletable = source_kind in MANAGED_UPLOAD_SOURCE_KINDS
                builtin = source_kind == "bundled" or not deletable
                file_name = source_path.name
                imports = _imports_for_source(source_path)
            else:
                source_kind = "compiled"
                source_group = ""
                relative_path = ""
                deletable = False
                builtin = False
                file_name = ""
                imports = []
            row_payload = {
                "name": mod_name,
                "file": file_name,
                "relative_path": relative_path,
                "objects": len(mod_record.objects),
                "traps": len(mod_record.notifications),
                "imports": imports,
                "builtin": builtin,
                "deletable": deletable,
                "source_kind": source_kind,
                "source_group": source_group,
            }
            rows_by_module[mod_name] = row_payload
            if deletable and relative_path:
                active_uploaded_paths.add(relative_path)
                active_uploaded_sources_by_module[mod_name] = row_payload

    from sqlalchemy import select
    from app.models import CompileRun
    error_rows_by_path: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    with bundle_service.session_factory() as session:
        failed_runs = session.scalars(
            select(CompileRun)
            .where(CompileRun.status == "failed")
            .order_by(CompileRun.id.desc())
            .limit(5)
        ).all()
        for run in failed_runs:
            requested = bundle_service._unique_mib_names(run.requested_mib_names_json or [])
            missing_deps = source_svc.missing_dependencies_from_error(run.error_text)
            status_label = "missing_deps" if missing_deps else "failed"
            for name in requested or [run.bundle_key or "compile-run"]:
                if name in rows_by_module:
                    continue
                source_path = source_svc.source_path_for_module(name)
                if source_path is None or not source_path.exists():
                    continue
                source_kind = source_svc.module_source_kind(source_path)
                if source_kind not in MANAGED_UPLOAD_SOURCE_KINDS:
                    continue
                relative_path = source_svc.relative_upload_path(source_path) or source_path.name
                if relative_path in active_uploaded_paths or relative_path in error_rows_by_path:
                    continue
                error_rows_by_path[relative_path] = {
                    "name": name,
                    "file": relative_path,
                    "error": run.error_text or "Compile failed.",
                    "status": status_label,
                    "missing_deps": missing_deps,
                    "deletable": True,
                    "source_kind": source_kind,
                    "source_group": source_svc.source_group_for_path(source_path, source_kind=source_kind),
                }

    available_names = source_svc.available_source_mib_names()
    for entry in source_svc.uploaded_source_inventory():
        relative_path = str(entry.get("relative_path") or "").strip()
        if not relative_path or relative_path in active_uploaded_paths or relative_path in error_rows_by_path:
            continue
        source_path = Path(entry["path"])
        source_kind = source_svc.module_source_kind(source_path)
        if source_kind != "uploaded":
            continue
        mib_name = str(entry.get("mib_name") or Path(relative_path).stem)
        active_source = active_uploaded_sources_by_module.get(mib_name)
        if active_source is not None and active_source.get("relative_path") != relative_path:
            active_relative_path = str(active_source.get("relative_path") or "")
            error_rows_by_path[relative_path] = {
                "name": mib_name,
                "file": relative_path,
                "error": (
                    "Another stored source for this MIB is active: "
                    f"{active_relative_path}. This copy is currently shadowed; "
                    "delete the duplicate or replace the active source."
                ),
                "status": "shadowed",
                "missing_deps": [],
                "deletable": True,
                "source_kind": source_kind,
                "source_group": str(entry.get("group") or ""),
                "active_relative_path": active_relative_path,
            }
            continue

        imports = _imports_for_source(source_path)
        missing_deps = [
            module_name
            for module_name in imports
            if module_name not in available_names and module_name not in BASE_IMPORT_MODULES
        ]
        error_rows_by_path[relative_path] = {
            "name": mib_name,
            "file": relative_path,
            "error": (
                "Stored source is not part of the active bundle. "
                + (
                    "Missing dependencies: " + ", ".join(missing_deps)
                    if missing_deps
                    else "Reload to compile it or delete it."
                )
            ),
            "status": "missing_deps" if missing_deps else "pending",
            "missing_deps": missing_deps,
            "deletable": True,
            "source_kind": source_kind,
            "source_group": str(entry.get("group") or ""),
        }

    mibs = list(rows_by_module.values())
    return {
        "loaded": len(mibs),
        "failed": len(error_rows_by_path),
        "mibs": mibs,
        "errors": list(error_rows_by_path.values()),
        "source_groups": source_svc.source_group_summary(mibs),
    }


def validate_upload_batch(
    uploaded: list[tuple[str, bytes]],
    *,
    source_group: str | None = None,
    settings: Settings,
    state: StateStore,
    bundle_service,
) -> dict[str, Any]:
    source_svc = _make_source_service(settings, state, bundle_service)
    mutation_svc = _make_mutation_service(settings, state, bundle_service, source_svc)
    return mutation_svc.validate_upload_batch(uploaded, source_group=source_group)


def upload(
    uploaded: list[tuple[str, bytes]],
    *,
    compile_mode: str = "full",
    compile_targets: list[str] | None = None,
    source_group: str | None = None,
    settings: Settings,
    state: StateStore,
    bundle_service,
) -> dict[str, Any]:
    _invalidate_source_cache()
    source_svc = _make_source_service(settings, state, bundle_service)
    mutation_svc = _make_mutation_service(settings, state, bundle_service, source_svc)
    return mutation_svc.save_uploaded_mibs(
        uploaded,
        compile_mode=compile_mode,
        compile_targets=compile_targets,
        source_group=source_group,
    )


def reload(*, settings: Settings, state: StateStore, bundle_service) -> dict[str, Any]:
    _invalidate_source_cache()
    source_svc = _make_source_service(settings, state, bundle_service)
    mutation_svc = _make_mutation_service(settings, state, bundle_service, source_svc)
    return mutation_svc.reload_uploaded_mib_bundle()


def fetch_dependencies(
    dependencies: list[str],
    *,
    settings: Settings,
    state: StateStore,
    bundle_service,
) -> dict[str, Any]:
    _invalidate_source_cache()
    source_svc = _make_source_service(settings, state, bundle_service)
    mutation_svc = _make_mutation_service(settings, state, bundle_service, source_svc)
    return mutation_svc.fetch_dependencies(dependencies)


def delete_mib(
    path: str,
    *,
    settings: Settings,
    state: StateStore,
    bundle_service,
) -> dict[str, Any]:
    _invalidate_source_cache()
    source_svc = _make_source_service(settings, state, bundle_service)
    mutation_svc = _make_mutation_service(settings, state, bundle_service, source_svc)
    return mutation_svc.delete_uploaded_mib(path)


def delete_mibs(
    paths: list[str],
    *,
    settings: Settings,
    state: StateStore,
    bundle_service,
) -> dict[str, Any]:
    _invalidate_source_cache()
    source_svc = _make_source_service(settings, state, bundle_service)
    mutation_svc = _make_mutation_service(settings, state, bundle_service, source_svc)
    return mutation_svc.delete_uploaded_mibs(paths)


def export_catalog(
    *,
    format: str = "json",
    modules: list[str] | None = None,
    notifications: list[str] | None = None,
    source_groups: list[str] | None = None,
    export_type: str = "catalog",
    settings: Settings,
    state: StateStore,
    bundle_service,
) -> dict[str, Any]:
    """Export MIB catalog from the live in-memory bundle."""
    bundle = get_bundle()
    if bundle is None:
        raise MibsError("No active MIB bundle is loaded.")
    from trishul_snmp.mib.registry import oid_to_string

    mod_filter = set(modules) if modules else None
    notif_filter = set(notifications) if notifications else None

    result_modules = []
    result_notifications = []
    result_objects = []

    for mod_name, mod_record in bundle.modules.items():
        if mod_filter and mod_name not in mod_filter:
            continue
        mod_notifications = [
            {
                "module": n.module,
                "name": n.name,
                "full_name": f"{n.module}::{n.name}",
                "oid": oid_to_string(n.oid),
                "description": n.description or "",
                "members": [{"module": m.module, "name": m.object} for m in (n.members or [])],
            }
            for n in mod_record.notifications.values()
            if not notif_filter or f"{n.module}::{n.name}" in notif_filter
        ]
        mod_objects = [
            {
                "module": o.module,
                "name": o.name,
                "full_name": f"{o.module}::{o.name}",
                "oid": oid_to_string(o.oid),
                "syntax": o.syntax or "",
                "nodetype": o.nodetype or "",
                "status": o.status or "",
                "description": o.description or "",
            }
            for o in mod_record.objects.values()
        ]
        result_modules.append({
            "module_name": mod_name,
            "object_count": len(mod_record.objects),
            "notification_count": len(mod_record.notifications),
        })
        result_notifications.extend(mod_notifications)
        result_objects.extend(mod_objects)

    if export_type in ("catalog", "notifications"):
        pass
    elif export_type == "objects":
        result_notifications = []
    elif export_type == "modules":
        result_notifications = []
        result_objects = []
    elif export_type == "summary":
        result_notifications = []
        result_objects = []

    return {
        "export_version": 2,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "filters": {
            "export_type": export_type,
            "requested_modules": list(mod_filter) if mod_filter else [],
            "requested_notifications": list(notif_filter) if notif_filter else [],
        },
        "summary": {
            "module_count": len(result_modules),
            "object_count": len(result_objects),
            "notification_count": len(result_notifications),
        },
        "modules": result_modules,
        "objects": result_objects,
        "notifications": result_notifications,
    }


def export_catalog_file(
    *,
    format: str = "json",
    modules: list[str] | None = None,
    notifications: list[str] | None = None,
    source_groups: list[str] | None = None,
    export_type: str = "catalog",
    settings: Settings,
    state: StateStore,
    bundle_service,
) -> dict[str, Any]:
    payload = export_catalog(
        format=format,
        modules=modules,
        notifications=notifications,
        source_groups=source_groups,
        export_type=export_type,
        settings=settings,
        state=state,
        bundle_service=bundle_service,
    )
    normalized_format = str(format or "json").strip().lower()
    basename = f"{export_type}"
    if normalized_format == "json":
        return {
            "filename": f"{basename}.json",
            "media_type": "application/json",
            "content": json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8"),
        }
    if normalized_format == "csv":
        import csv, io
        out = io.StringIO()
        writer = csv.writer(out)
        if export_type == "notifications":
            writer.writerow(["module", "name", "oid", "description"])
            for n in payload.get("notifications", []):
                writer.writerow([n["module"], n["name"], n["oid"], n.get("description", "")])
        else:
            writer.writerow(["module", "name", "oid", "type"])
            for o in payload.get("objects", []):
                writer.writerow([o["module"], o["name"], o["oid"], o.get("nodetype", "")])
        return {
            "filename": f"{basename}.csv",
            "media_type": "text/csv",
            "content": out.getvalue().encode("utf-8"),
        }
    raise MibsError("Unsupported catalog export format. Use json or csv.")
