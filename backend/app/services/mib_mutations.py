from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.models import BundleSet
from app.services.bundles import BundleCompileRequest, BundleServiceError


class ShellMibMutationService:
    def __init__(
        self,
        *,
        error_cls,
        bundle_service,
        session_factory,
        upload_dir,
        bundled_mibs_dir,
        emit_operation_log,
        increment_counter,
        load_mib_status,
        analyze_upload_batch,
        apply_upload_batch_policy,
        remote_fetch_policy,
        select_upload_targets,
        normalize_source_group,
        reset_source_caches,
        compile_target_mib_names,
        compile_source_dirs,
        uploaded_bundle_label,
        materialize_cached_remote_modules,
        upload_result_rows,
        dependency_fetch_payload,
        missing_dependencies_from_error,
        uploaded_mib_names,
        reload_uploaded_mibs,
        uploaded_target_path,
        relative_upload_path,
        prune_empty_upload_dirs,
        active_source_map,
        promoted_active_sources,
        available_source_mib_names,
        mib_reload_count_key: str,
    ) -> None:
        self.error_cls = error_cls
        self.bundle_service = bundle_service
        self.session_factory = session_factory
        self.upload_dir = upload_dir
        self.bundled_mibs_dir = bundled_mibs_dir
        self.emit_operation_log = emit_operation_log
        self.increment_counter = increment_counter
        self.load_mib_status = load_mib_status
        self.analyze_upload_batch = analyze_upload_batch
        self.apply_upload_batch_policy = apply_upload_batch_policy
        self.remote_fetch_policy = remote_fetch_policy
        self.select_upload_targets = select_upload_targets
        self.normalize_source_group = normalize_source_group
        self.reset_source_caches = reset_source_caches
        self.compile_target_mib_names = compile_target_mib_names
        self.compile_source_dirs = compile_source_dirs
        self.uploaded_bundle_label = uploaded_bundle_label
        self.materialize_cached_remote_modules = materialize_cached_remote_modules
        self.upload_result_rows = upload_result_rows
        self.dependency_fetch_payload = dependency_fetch_payload
        self.missing_dependencies_from_error = missing_dependencies_from_error
        self.uploaded_mib_names = uploaded_mib_names
        self.reload_uploaded_mibs = reload_uploaded_mibs
        self.uploaded_target_path = uploaded_target_path
        self.relative_upload_path = relative_upload_path
        self.prune_empty_upload_dirs = prune_empty_upload_dirs
        self.active_source_map = active_source_map
        self.promoted_active_sources = promoted_active_sources
        self.available_source_mib_names = available_source_mib_names
        self.mib_reload_count_key = mib_reload_count_key

    def validate_upload_batch(
        self,
        uploaded: list[tuple[str, bytes]],
        *,
        source_group: str | None = None,
    ) -> dict[str, Any]:
        payload = self.analyze_upload_batch(uploaded, source_group=source_group)
        payload["dependency_fetch"] = self.remote_fetch_policy()
        self.apply_upload_batch_policy(payload, policy=payload["dependency_fetch"])
        return payload

    def save_uploaded_mibs(
        self,
        uploaded: list[tuple[str, bytes]],
        *,
        compile_mode: str = "full",
        compile_targets: list[str] | None = None,
        source_group: str | None = None,
    ) -> dict[str, Any]:
        if not uploaded:
            raise self.error_cls("No files were uploaded.")

        batch = self.analyze_upload_batch(uploaded, source_group=source_group)
        remote_policy = self.remote_fetch_policy()
        self.apply_upload_batch_policy(batch, policy=remote_policy)
        if any(not entry["valid"] for entry in batch["files"]):
            raise self.error_cls("Upload only accepts .mib, .txt, or .my files.")
        if str(compile_mode or "full").strip().lower() != "partial" and not batch.get("can_upload"):
            raise self.error_cls(
                str(
                    batch.get("upload_blocked_reason")
                    or "Full upload is blocked until dependency issues are resolved."
                )
            )

        selected_targets = self.select_upload_targets(
            batch=batch,
            compile_mode=compile_mode,
            compile_targets=compile_targets,
        )
        compile_mode_label = "partial" if str(compile_mode).strip().lower() == "partial" else "full"
        saved_files: list[str] = []
        target_group = self.normalize_source_group(source_group)
        target_dir = self.upload_dir() / Path(target_group)
        target_dir.mkdir(parents=True, exist_ok=True)
        for entry, (_filename, content) in zip(batch["files"], uploaded, strict=False):
            target_relative_path = str(entry.get("target_relative_path") or "").strip()
            if not target_relative_path:
                continue
            target = self.uploaded_target_path(target_relative_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            saved_files.append(target_relative_path)
        self.reset_source_caches()
        mib_names = self.compile_target_mib_names(selected_targets)
        try:
            self.emit_operation_log(
                (
                    f"Compiling uploaded MIBs: mode={compile_mode_label} files={saved_files} "
                    f"selected_targets={selected_targets} compile_targets={mib_names} "
                    f"remote_fetch={remote_policy['enabled']}"
                ),
            )
            compile_result = self.bundle_service.compile_bundle(
                BundleCompileRequest(
                    mib_names=mib_names,
                    mib_dirs=self.compile_source_dirs(),
                    activate=True,
                    label=self.uploaded_bundle_label(target_group),
                    online=bool(remote_policy["enabled"]),
                    remote_sources=list(remote_policy["sources"]),
                )
            )
            self.materialize_cached_remote_modules(
                compile_result.get("remote_modules") or [],
                bundle_set_id=(compile_result.get("bundle") or {}).get("id"),
            )
            results = self.upload_result_rows(
                batch=batch,
                selected_targets=selected_targets,
                status="loaded",
            )
            dependency_fetch = self.dependency_fetch_payload(
                policy=remote_policy,
                attempted=batch["global_missing_deps"],
                resolved=compile_result.get("remote_modules") or [],
            )
        except BundleServiceError as exc:
            self.emit_operation_log(
                f"Uploaded MIB compile failed for files={saved_files}: {exc}",
                level="ERROR",
            )
            results = self.upload_result_rows(
                batch=batch,
                selected_targets=selected_targets,
                status="failed",
                error=str(exc),
            )
            dependency_fetch = self.dependency_fetch_payload(
                policy=remote_policy,
                attempted=batch["global_missing_deps"],
                failed=self.missing_dependencies_from_error(str(exc)) or batch["global_missing_deps"],
            )

        return {
            "results": results,
            "compile_mode": compile_mode_label,
            "compiled_mibs": selected_targets,
            "dependency_fetch": dependency_fetch,
            "source_group": target_group,
        }

    def reload_uploaded_mib_bundle(self) -> dict[str, Any]:
        uploaded_mib_names = self.uploaded_mib_names()
        if not uploaded_mib_names:
            try:
                self.emit_operation_log("No uploaded MIB sources remain; reactivating bundled starter bundle.")
                self.activate_bundled_starter_bundle()
            except BundleServiceError as exc:
                raise self.error_cls(str(exc)) from exc
            self.increment_counter(self.mib_reload_count_key, 1)
            status = self.load_mib_status()
            return {
                "loaded": status["loaded"],
                "failed": status["failed"],
                "dependency_fetch": self.dependency_fetch_payload(
                    policy=self.remote_fetch_policy(),
                ),
            }
        mib_names = self.compile_target_mib_names(uploaded_mib_names)
        remote_policy = self.remote_fetch_policy()
        try:
            self.emit_operation_log(
                (
                    f"Reloading uploaded MIBs: uploaded={uploaded_mib_names} compile_targets={mib_names} "
                    f"remote_fetch={remote_policy['enabled']}"
                ),
            )
            compile_result = self.bundle_service.compile_bundle(
                BundleCompileRequest(
                    mib_names=mib_names,
                    mib_dirs=self.compile_source_dirs(),
                    activate=True,
                    label=f"active-aggregate-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}",
                    online=bool(remote_policy["enabled"]),
                    remote_sources=list(remote_policy["sources"]),
                )
            )
            self.materialize_cached_remote_modules(
                compile_result.get("remote_modules") or [],
                bundle_set_id=(compile_result.get("bundle") or {}).get("id"),
            )
        except BundleServiceError as exc:
            self.emit_operation_log(
                f"Reloaded MIB compile failed for mib_names={mib_names}: {exc}",
                level="ERROR",
            )
            raise self.error_cls(str(exc)) from exc
        self.increment_counter(self.mib_reload_count_key, 1)
        status = self.load_mib_status()
        return {
            "loaded": status["loaded"],
            "failed": status["failed"],
            "dependency_fetch": self.dependency_fetch_payload(
                policy=remote_policy,
                resolved=compile_result.get("remote_modules") or [],
            ),
        }

    def activate_bundled_starter_bundle(self) -> dict[str, Any] | None:
        with self.session_factory() as session:
            starter_bundle = session.scalar(
                select(BundleSet)
                .where(BundleSet.label == "Bundled Starter MIBs")
                .order_by(BundleSet.id.desc())
                .limit(1)
            )

        if starter_bundle is not None:
            return self.bundle_service.activate_bundle(starter_bundle.id)

        starter_mibs = self.bundle_service.bundled_mib_names()
        if not starter_mibs:
            return None

        result = self.bundle_service.compile_bundle(
            BundleCompileRequest(
                mib_names=starter_mibs,
                mib_dirs=[str(self.bundled_mibs_dir())],
                activate=True,
                label="Bundled Starter MIBs",
            )
        )
        return result.get("activation")

    def _collect_delete_requests(
        self,
        filenames: list[str],
    ) -> list[tuple[Path, str, Path, bytes]]:
        requested: list[tuple[Path, str, Path, bytes]] = []
        seen: set[str] = set()
        for raw_name in filenames or []:
            candidate = str(raw_name or "").strip().replace("\\", "/")
            if not candidate or candidate in seen:
                continue
            target = self.uploaded_target_path(candidate)
            if not target.exists() or not target.is_file():
                raise self.error_cls(f"MIB file {candidate} does not exist.")
            relative_path = self.relative_upload_path(target) or target.name
            requested.append((target, relative_path, target.parent, target.read_bytes()))
            seen.add(candidate)
        return requested

    def _restore_deleted_sources(
        self,
        requested: list[tuple[Path, str, Path, bytes]],
    ) -> None:
        for target, _relative_path, parent_dir, content in requested:
            if target.exists():
                continue
            parent_dir.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        self.reset_source_caches()

    def _prune_deleted_source_dirs(
        self,
        requested: list[tuple[Path, str, Path, bytes]],
    ) -> None:
        for _target, _relative_path, parent_dir, _content in requested:
            self.prune_empty_upload_dirs(parent_dir)

    def delete_uploaded_mib(
        self,
        filename: str,
        *,
        reload_after_delete: bool = True,
    ) -> dict[str, Any]:
        requested = self._collect_delete_requests([filename])
        target, relative_path, parent_dir, _original_content = requested[0]
        before_active_sources = self.active_source_map()

        self.emit_operation_log(f"Deleting uploaded MIB source {relative_path}.")
        target.unlink()
        self.reset_source_caches()

        reload_result: dict[str, Any] | None = None
        if reload_after_delete:
            try:
                reload_result = self.reload_uploaded_mibs()
            except Exception as exc:
                self._restore_deleted_sources(requested)
                self.emit_operation_log(
                    f"Delete rollback restored {relative_path} after reload failure: {exc}",
                    level="ERROR",
                )
                raise self.error_cls(
                    (
                        f"Could not remove {relative_path} cleanly because rebuilding the active bundle failed: {exc}. "
                        "The source file has been restored."
                    )
                ) from exc

        self._prune_deleted_source_dirs(requested)
        response: dict[str, Any] = {
            "status": "deleted",
            "filename": relative_path,
            "reload_applied": bool(reload_after_delete),
        }
        if reload_result is not None:
            response["reload"] = reload_result
            response["loaded"] = reload_result.get("loaded", 0)
            response["failed"] = reload_result.get("failed", 0)
            response["dependency_fetch"] = reload_result.get("dependency_fetch", {})
            promoted_sources = self.promoted_active_sources(
                before_active_sources=before_active_sources,
                after_active_sources=self.active_source_map(),
                deleted_paths=[relative_path],
            )
            if promoted_sources:
                response["promoted_sources"] = promoted_sources
        return response

    def delete_uploaded_mibs(self, filenames: list[str]) -> dict[str, Any]:
        requested = self._collect_delete_requests(filenames)
        if not requested:
            raise self.error_cls("Select at least one uploaded MIB file to delete.")

        deleted_files = [relative_path for _target, relative_path, _parent, _content in requested]
        before_active_sources = self.active_source_map()
        self.emit_operation_log(
            f"Deleting uploaded MIB sources: {', '.join(deleted_files)}.",
        )

        try:
            for target, _relative_path, _parent_dir, _content in requested:
                target.unlink()
            self.reset_source_caches()
            reload_result = self.reload_uploaded_mibs()
        except Exception as exc:
            self._restore_deleted_sources(requested)
            self.emit_operation_log(
                (
                    f"Bulk delete rollback restored {', '.join(deleted_files)} "
                    f"after reload failure: {exc}"
                ),
                level="ERROR",
            )
            raise self.error_cls(
                (
                    f"Could not remove {len(requested)} MIB sources cleanly because rebuilding the active bundle failed: {exc}. "
                    "The source files have been restored."
                )
            ) from exc

        self._prune_deleted_source_dirs(requested)

        response = {
            "status": "deleted",
            "deleted_count": len(deleted_files),
            "deleted_files": deleted_files,
            "reload_applied": True,
            "reload": reload_result,
            "loaded": reload_result.get("loaded", 0),
            "failed": reload_result.get("failed", 0),
            "dependency_fetch": reload_result.get("dependency_fetch", {}),
        }
        promoted_sources = self.promoted_active_sources(
            before_active_sources=before_active_sources,
            after_active_sources=self.active_source_map(),
            deleted_paths=deleted_files,
        )
        if promoted_sources:
            response["promoted_sources"] = promoted_sources
        return response

    def fetch_dependencies(self, dependencies: list[str]) -> dict[str, Any]:
        available = self.available_source_mib_names()
        cached = [
            dep
            for dep in dict.fromkeys(str(dep).strip() for dep in dependencies if str(dep).strip())
            if dep in available
        ]
        return {
            "enabled": False,
            "auto_enabled": False,
            "using_default_sources": False,
            "sources": [],
            "resolved": [],
            "downloaded": [],
            "cached": cached,
            "failed": [
                dep
                for dep in dict.fromkeys(str(dep).strip() for dep in dependencies if str(dep).strip())
                if dep not in available
            ],
        }
