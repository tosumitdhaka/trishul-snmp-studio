from __future__ import annotations

import json

import pytest

pytestmark = pytest.mark.unit


def _activate_mibs_bundle(isolated_db):
    from app.services.bundles import BundleCompileRequest, BundleService

    settings = isolated_db["settings"]
    bundle_service = BundleService(settings)
    bundle_service.compile_bundle(
        BundleCompileRequest(mib_names=["IF-MIB", "SNMPv2-MIB"], activate=True)
    )
    return bundle_service


def test_validate_upload_batch_surfaces_missing_dependencies(isolated_db):
    from app.services import mibs_service
    from app.services.bundles import BundleService
    from app.services.state_store import StateStore

    settings = isolated_db["settings"]
    session_factory = isolated_db["session_factory"]
    state = StateStore(session_factory)
    bundle_service = BundleService(settings)

    payload = mibs_service.validate_upload_batch(
        [
            (
                "EXAMPLE-MIB.mib",
                b"""
EXAMPLE-MIB DEFINITIONS ::= BEGIN

IMPORTS
    MODULE-IDENTITY
        FROM SNMPv2-SMI
    MissingThing
        FROM MISSING-DEP-MIB;

exampleMib MODULE-IDENTITY
    LAST-UPDATED "202605120000Z"
    ORGANIZATION "Tests"
    DESCRIPTION "Validation coverage."
    ::= { 1 3 6 1 4 1 99999 1 }

END
""",
            )
        ],
        settings=settings,
        state=state,
        bundle_service=bundle_service,
    )

    assert payload["can_upload"] is False
    assert payload["global_missing_deps"] == ["MISSING-DEP-MIB"]
    assert payload["files"][0]["mib_name"] == "EXAMPLE-MIB"
    assert payload["files"][0]["missing_deps"] == ["MISSING-DEP-MIB"]
    assert payload["files"][0]["partial_blockers"] == ["MISSING-DEP-MIB"]
    assert payload["files"][0]["ready_for_partial"] is False
    assert payload["partial_compile"]["ready_mibs"] == []
    assert payload["partial_compile"]["blocked_mibs"] == ["EXAMPLE-MIB"]
    assert payload["dependency_fetch"]["auto_enabled"] is False
    assert "auto-fetch is disabled" in payload["upload_blocked_reason"]


def test_validate_upload_batch_allows_full_upload_when_auto_fetch_enabled(isolated_db):
    from app.models import AppSetting
    from app.services import mibs_service
    from app.services.bundles import BundleService
    from app.services.state_store import StateStore, _MIB_AUTO_FETCH_KEY

    settings = isolated_db["settings"]
    session_factory = isolated_db["session_factory"]

    with session_factory() as session:
        session.add(AppSetting(key=_MIB_AUTO_FETCH_KEY, value_json=True))
        session.commit()

    state = StateStore(session_factory)
    bundle_service = BundleService(settings)

    payload = mibs_service.validate_upload_batch(
        [
            (
                "EXAMPLE-MIB.mib",
                b"""
EXAMPLE-MIB DEFINITIONS ::= BEGIN

IMPORTS
    MODULE-IDENTITY
        FROM SNMPv2-SMI
    MissingThing
        FROM MISSING-DEP-MIB;

exampleMib MODULE-IDENTITY
    LAST-UPDATED "202605120000Z"
    ORGANIZATION "Tests"
    DESCRIPTION "Validation coverage."
    ::= { 1 3 6 1 4 1 99999 1 }

END
""",
            )
        ],
        settings=settings,
        state=state,
        bundle_service=bundle_service,
    )

    assert payload["can_upload"] is True
    assert payload["dependency_fetch"]["auto_enabled"] is True
    assert payload["upload_blocked_reason"] is None


def test_validate_upload_batch_reports_duplicate_shadowing_by_source_group(isolated_db):
    from app.services import mibs_service
    from app.services.bundles import BundleService
    from app.services.state_store import StateStore

    settings = isolated_db["settings"]
    session_factory = isolated_db["session_factory"]
    existing_common = settings.data_dir / "mibs" / "common" / "JUNIPER-MAG-MIB.mib"
    existing_common.parent.mkdir(parents=True, exist_ok=True)
    existing_common.write_text(
        """
JUNIPER-MAG-MIB DEFINITIONS ::= BEGIN

magRoot OBJECT IDENTIFIER ::= { 1 3 6 1 4 1 2636 3 65 1 }

END
""".strip()
        + "\n"
    )

    state = StateStore(session_factory)
    bundle_service = BundleService(settings)

    payload = mibs_service.validate_upload_batch(
        [
            (
                "JUNIPER-MAG-MIB.txt",
                b"""
JUNIPER-MAG-MIB DEFINITIONS ::= BEGIN

magRoot OBJECT IDENTIFIER ::= { 1 3 6 1 4 1 2636 3 65 1 }

END
""",
            )
        ],
        source_group="juniper",
        settings=settings,
        state=state,
        bundle_service=bundle_service,
    )

    assert payload["can_upload"] is True
    assert payload["duplicate_modules"] == [
        {
            "mib_name": "JUNIPER-MAG-MIB",
            "target_relative_path": "juniper/JUNIPER-MAG-MIB.txt",
            "source_group": "juniper",
            "resolution_status": "shadowed",
            "predicted_active_relative_path": "common/JUNIPER-MAG-MIB.mib",
            "predicted_active_source_group": "common",
            "duplicate_sources": [
                {
                    "relative_path": "common/JUNIPER-MAG-MIB.mib",
                    "source_group": "common",
                }
            ],
            "warnings": [
                (
                    "Another stored source has higher precedence and will remain active: "
                    "common/JUNIPER-MAG-MIB.mib. This upload will be stored but shadowed "
                    "until the higher-precedence copy is deleted or replaced."
                )
            ],
        }
    ]
    assert payload["files"][0]["duplicate_resolution"]["resolution_status"] == "shadowed"
    assert (
        payload["files"][0]["duplicate_resolution"]["predicted_active_relative_path"]
        == "common/JUNIPER-MAG-MIB.mib"
    )


def test_validate_upload_batch_canonicalizes_target_path_from_declared_mib_name(isolated_db):
    from app.services import mibs_service
    from app.services.bundles import BundleService
    from app.services.state_store import StateStore

    settings = isolated_db["settings"]
    session_factory = isolated_db["session_factory"]
    state = StateStore(session_factory)
    bundle_service = BundleService(settings)

    payload = mibs_service.validate_upload_batch(
        [
            (
                "vendor-copy-2026.txt",
                b"""
CANONICAL-UPLOAD-MIB DEFINITIONS ::= BEGIN

IMPORTS
    enterprises FROM SNMPv2-SMI;

canonicalUploadNode OBJECT IDENTIFIER ::= { enterprises 424242 }

END
""",
            )
        ],
        source_group="vendor",
        settings=settings,
        state=state,
        bundle_service=bundle_service,
    )

    assert payload["files"][0]["safe_name"] == "vendor-copy-2026.txt"
    assert payload["files"][0]["storage_name"] == "CANONICAL-UPLOAD-MIB.txt"
    assert payload["files"][0]["target_relative_path"] == "vendor/CANONICAL-UPLOAD-MIB.txt"


def test_upload_uses_ready_targets_and_setting_driven_remote_fetch(isolated_db, monkeypatch):
    from app.models import AppSetting
    from app.services import mibs_service
    from app.services.bundles import BundleService
    from app.services.state_store import StateStore, _MIB_AUTO_FETCH_KEY

    settings = isolated_db["settings"]
    session_factory = isolated_db["session_factory"]

    with session_factory() as session:
        session.add(AppSetting(key=_MIB_AUTO_FETCH_KEY, value_json=True))
        session.commit()

    state = StateStore(session_factory)
    bundle_service = BundleService(settings)

    cached_remote_source = settings.tsmi_cache_dir / "raw" / "https_example.invalid_MISSING-DEP-MIB.mib"
    cached_remote_source.parent.mkdir(parents=True, exist_ok=True)
    cached_remote_source.write_text(
        """
MISSING-DEP-MIB DEFINITIONS ::= BEGIN

missingDepNode OBJECT IDENTIFIER ::= { 1 3 6 1 4 1 99999 99 }

END
""".strip()
        + "\n"
    )
    captured: dict[str, object] = {}

    def fake_compile_bundle(request):
        captured["request"] = request
        return {
            "bundle": {"id": 1},
            "remote_modules": ["MISSING-DEP-MIB"],
        }

    monkeypatch.setattr(bundle_service, "compile_bundle", fake_compile_bundle)

    result = mibs_service.upload(
        [
            (
                "READY-MIB.mib",
                b"""
READY-MIB DEFINITIONS ::= BEGIN

readyNode OBJECT IDENTIFIER ::= { 1 3 6 1 4 1 99999 1 }

END
""",
            ),
            (
                "BLOCKED-MIB.mib",
                b"""
BLOCKED-MIB DEFINITIONS ::= BEGIN

IMPORTS
    MissingThing
        FROM MISSING-DEP-MIB;

blockedNode OBJECT IDENTIFIER ::= { 1 3 6 1 4 1 99999 2 }

END
""",
            ),
        ],
        compile_mode="partial",
        settings=settings,
        state=state,
        bundle_service=bundle_service,
    )

    request = captured["request"]
    assert request.online is True
    assert request.remote_sources == []
    assert "READY-MIB" in request.mib_names
    assert "BLOCKED-MIB" not in request.mib_names
    assert request.label.startswith("common-upload-")
    assert result["compile_mode"] == "partial"
    assert result["compiled_mibs"] == ["READY-MIB"]
    assert any(
        row["status"] == "loaded" and row["mib_name"] == "READY-MIB"
        for row in result["results"]
    )
    assert any(
        row["status"] == "skipped" and row["mib_name"] == "BLOCKED-MIB"
        for row in result["results"]
    )
    assert result["dependency_fetch"]["enabled"] is True
    assert result["dependency_fetch"]["using_default_sources"] is True
    assert result["dependency_fetch"]["resolved"] == ["MISSING-DEP-MIB"]
    assert (settings.data_dir / "mibs" / "auto-fetched" / "MISSING-DEP-MIB.mib").exists()


def test_reload_without_uploaded_mibs_reverts_to_bundled_starter_bundle(isolated_db):
    from app.services import mibs_service
    from app.services.bundles import BundleService
    from app.services.state_store import StateStore

    settings = isolated_db["settings"]
    session_factory = isolated_db["session_factory"]
    state = StateStore(session_factory)
    bundle_service = BundleService(settings)

    result = mibs_service.reload(settings=settings, state=state, bundle_service=bundle_service)
    effective_bundle = BundleService(settings).get_effective_bundle_summary()

    assert result["loaded"] >= 1
    assert result["failed"] == 0
    assert effective_bundle is not None
    assert effective_bundle["label"] == "Bundled Starter MIBs"
    assert effective_bundle["is_active"] is True
    assert any(module["module_name"] == "IF-MIB" for module in effective_bundle["modules"])


def test_upload_saves_into_source_group_and_reports_group_inventory(isolated_db, monkeypatch):
    from app.services import mibs_service
    from app.services.bundles import BundleService
    from app.services.state_store import StateStore

    settings = isolated_db["settings"]
    session_factory = isolated_db["session_factory"]
    state = StateStore(session_factory)
    bundle_service = BundleService(settings)

    captured: dict[str, object] = {}

    def fake_compile_bundle(request):
        captured["request"] = request
        return {
            "bundle": {"id": 1},
            "remote_modules": [],
        }

    monkeypatch.setattr(bundle_service, "compile_bundle", fake_compile_bundle)

    result = mibs_service.upload(
        [
            (
                "ERICSSON-TEST-MIB.mib",
                b"""
ERICSSON-TEST-MIB DEFINITIONS ::= BEGIN

testNode OBJECT IDENTIFIER ::= { 1 3 6 1 4 1 99999 7 }

END
""",
            )
        ],
        source_group="ericsson/core",
        settings=settings,
        state=state,
        bundle_service=bundle_service,
    )

    request = captured["request"]
    assert request.mib_dirs[0].endswith("/mibs/ericsson/core")
    assert request.mib_dirs[-1].endswith("/mibs_bundled")
    assert request.label.startswith("ericsson-core-upload-")
    assert result["source_group"] == "ericsson/core"
    assert (settings.data_dir / "mibs" / "ericsson" / "core" / "ERICSSON-TEST-MIB.mib").exists()

    status = mibs_service.get_status(settings=settings, state=state, bundle_service=bundle_service)
    group_rows = {item["name"]: item for item in status["source_groups"]}
    assert group_rows["ericsson/core"]["file_count"] == 1
    assert group_rows["ericsson/core"]["mib_count"] == 1


def test_upload_compiles_when_filename_differs_from_declared_mib_name(isolated_db):
    from app.services import mibs_service
    from app.services.bundles import BundleService
    from app.services.state_store import StateStore

    settings = isolated_db["settings"]
    session_factory = isolated_db["session_factory"]
    state = StateStore(session_factory)
    bundle_service = BundleService(settings)

    result = mibs_service.upload(
        [
            (
                "vendor-copy-2026.txt",
                b"""
CANONICAL-UPLOAD-MIB DEFINITIONS ::= BEGIN

IMPORTS
    enterprises FROM SNMPv2-SMI;

canonicalUploadNode OBJECT IDENTIFIER ::= { enterprises 424242 }

END
""",
            )
        ],
        source_group="vendor",
        settings=settings,
        state=state,
        bundle_service=bundle_service,
    )

    assert result["results"][0]["status"] == "loaded"
    assert (settings.data_dir / "mibs" / "vendor" / "CANONICAL-UPLOAD-MIB.txt").exists()
    assert (settings.data_dir / "mibs" / "vendor" / "vendor-copy-2026.txt").exists() is False

    status = mibs_service.get_status(settings=settings, state=state, bundle_service=bundle_service)
    loaded_by_name = {row["name"]: row for row in status["mibs"]}
    assert loaded_by_name["CANONICAL-UPLOAD-MIB"]["relative_path"] == "vendor/CANONICAL-UPLOAD-MIB.txt"


def test_status_only_reports_uploaded_compile_failures(isolated_db):
    from app.services import mibs_service
    from app.services.bundles import BundleService
    from app.services.state_store import StateStore

    settings = isolated_db["settings"]
    session_factory = isolated_db["session_factory"]
    state = StateStore(session_factory)
    bundle_service = BundleService(settings)

    result = mibs_service.upload(
        [
            (
                "BROKEN-MIB.mib",
                b"""
BROKEN-MIB DEFINITIONS ::= BEGIN

brokenNode OBJECT IDENTIFIER ::= { 1 3 6 1 4 1 99999

END
""",
            )
        ],
        settings=settings,
        state=state,
        bundle_service=bundle_service,
    )

    assert result["results"][0]["status"] == "failed"

    status = mibs_service.get_status(settings=settings, state=state, bundle_service=bundle_service)
    assert status["loaded"] == 0
    assert status["failed"] == 1
    assert status["errors"][0]["name"] == "BROKEN-MIB"
    assert status["errors"][0]["file"] == "common/BROKEN-MIB.mib"
    assert status["errors"][0]["deletable"] is True


def test_status_reports_shadowed_duplicate_sources(isolated_db):
    from app.services import mibs_service
    from app.services.bundles import BundleService
    from app.services.state_store import StateStore

    settings = isolated_db["settings"]
    session_factory = isolated_db["session_factory"]
    state = StateStore(session_factory)
    bundle_service = BundleService(settings)

    result = mibs_service.upload(
        [
            (
                "JUNIPER-MAG-MIB.mib",
                b"""
JUNIPER-MAG-MIB DEFINITIONS ::= BEGIN

IMPORTS
    enterprises FROM SNMPv2-SMI;

juniperMagNode OBJECT IDENTIFIER ::= { enterprises 99999 }

END
""",
            )
        ],
        source_group="common",
        settings=settings,
        state=state,
        bundle_service=bundle_service,
    )

    assert result["results"][0]["status"] == "loaded"

    shadowed_path = settings.data_dir / "mibs" / "juniper" / "JUNIPER-MAG-MIB.mib"
    shadowed_path.parent.mkdir(parents=True, exist_ok=True)
    shadowed_path.write_text(
        "JUNIPER-MAG-MIB DEFINITIONS ::= BEGIN\n"
        "IMPORTS enterprises FROM SNMPv2-SMI;\n"
        "juniperMagShadowedNode OBJECT IDENTIFIER ::= { enterprises 99998 }\n"
        "END\n"
    )
    mibs_service._invalidate_source_cache()

    status = mibs_service.get_status(
        settings=settings,
        state=state,
        bundle_service=bundle_service,
    )

    errors_by_file = {row["file"]: row for row in status["errors"]}
    assert status["loaded"] >= 1
    assert "juniper/JUNIPER-MAG-MIB.mib" in errors_by_file
    assert errors_by_file["juniper/JUNIPER-MAG-MIB.mib"]["status"] == "shadowed"
    assert (
        errors_by_file["juniper/JUNIPER-MAG-MIB.mib"]["active_relative_path"]
        == "common/JUNIPER-MAG-MIB.mib"
    )


def test_delete_uploaded_mib_supports_grouped_relative_paths(isolated_db):
    from app.services import mibs_service
    from app.services.bundles import BundleService
    from app.services.state_store import StateStore

    settings = isolated_db["settings"]
    session_factory = isolated_db["session_factory"]
    grouped_path = settings.data_dir / "mibs" / "juniper" / "JUNIPER-TEST-MIB.mib"
    grouped_path.parent.mkdir(parents=True, exist_ok=True)
    grouped_path.write_text(
        """
JUNIPER-TEST-MIB DEFINITIONS ::= BEGIN

testNode OBJECT IDENTIFIER ::= { 1 3 6 1 4 1 99999 8 }

END
""".strip()
        + "\n"
    )

    state = StateStore(session_factory)
    bundle_service = BundleService(settings)

    deleted = mibs_service.delete_mib(
        "juniper/JUNIPER-TEST-MIB.mib",
        settings=settings,
        state=state,
        bundle_service=bundle_service,
    )

    assert deleted["filename"] == "juniper/JUNIPER-TEST-MIB.mib"
    assert deleted["reload_applied"] is True
    assert "loaded" in deleted
    assert grouped_path.exists() is False


def test_delete_uploaded_mib_restores_file_when_rebuild_fails(isolated_db, monkeypatch):
    from app.services import mibs_service
    from app.services.bundles import BundleService, BundleServiceError
    from app.services.mibs_service import MibsError
    from app.services.state_store import StateStore

    settings = isolated_db["settings"]
    session_factory = isolated_db["session_factory"]
    mib_path = settings.data_dir / "mibs" / "ericsson" / "ERICSSON-ROLLBACK-MIB.mib"
    mib_path.parent.mkdir(parents=True, exist_ok=True)
    mib_path.write_text(
        "ERICSSON-ROLLBACK-MIB DEFINITIONS ::= BEGIN\n"
        "rollbackNode OBJECT IDENTIFIER ::= { 1 3 6 1 4 1 99999 9 }\n"
        "END\n"
    )

    state = StateStore(session_factory)
    bundle_service = BundleService(settings)
    monkeypatch.setattr(
        bundle_service,
        "compile_bundle",
        lambda request: (_ for _ in ()).throw(BundleServiceError("simulated rebuild failure")),
    )

    with pytest.raises(MibsError, match="restored"):
        mibs_service.delete_mib(
            "ericsson/ERICSSON-ROLLBACK-MIB.mib",
            settings=settings,
            state=state,
            bundle_service=bundle_service,
        )

    assert mib_path.exists() is True


def test_delete_uploaded_mibs_delete_files_and_prune_empty_dir(isolated_db):
    from app.services import mibs_service
    from app.services.bundles import BundleService
    from app.services.state_store import StateStore

    settings = isolated_db["settings"]
    session_factory = isolated_db["session_factory"]
    first_path = settings.data_dir / "mibs" / "juniper" / "JUNIPER-A.mib"
    second_path = settings.data_dir / "mibs" / "juniper" / "JUNIPER-B.mib"
    first_path.parent.mkdir(parents=True, exist_ok=True)
    first_path.write_text(
        "JUNIPER-A DEFINITIONS ::= BEGIN\n"
        "juniperANode OBJECT IDENTIFIER ::= { 1 3 6 1 4 1 99999 10 }\n"
        "END\n"
    )
    second_path.write_text(
        "JUNIPER-B DEFINITIONS ::= BEGIN\n"
        "juniperBNode OBJECT IDENTIFIER ::= { 1 3 6 1 4 1 99999 11 }\n"
        "END\n"
    )

    state = StateStore(session_factory)
    bundle_service = BundleService(settings)

    deleted = mibs_service.delete_mibs(
        ["juniper/JUNIPER-A.mib", "juniper/JUNIPER-B.mib"],
        settings=settings,
        state=state,
        bundle_service=bundle_service,
    )

    assert first_path.exists() is False
    assert second_path.exists() is False
    assert first_path.parent.exists() is False
    assert deleted["reload_applied"] is True
    assert "loaded" in deleted


def test_delete_uploaded_mibs_restore_files_when_rebuild_fails(isolated_db, monkeypatch):
    from app.services import mibs_service
    from app.services.bundles import BundleService, BundleServiceError
    from app.services.mibs_service import MibsError
    from app.services.state_store import StateStore

    settings = isolated_db["settings"]
    session_factory = isolated_db["session_factory"]
    first_path = settings.data_dir / "mibs" / "ericsson" / "ERICSSON-A.mib"
    second_path = settings.data_dir / "mibs" / "ericsson" / "ERICSSON-B.mib"
    first_path.parent.mkdir(parents=True, exist_ok=True)
    first_path.write_text(
        "ERICSSON-A DEFINITIONS ::= BEGIN\n"
        "ericssonANode OBJECT IDENTIFIER ::= { 1 3 6 1 4 1 99999 12 }\n"
        "END\n"
    )
    second_path.write_text(
        "ERICSSON-B DEFINITIONS ::= BEGIN\n"
        "ericssonBNode OBJECT IDENTIFIER ::= { 1 3 6 1 4 1 99999 13 }\n"
        "END\n"
    )

    state = StateStore(session_factory)
    bundle_service = BundleService(settings)
    monkeypatch.setattr(
        bundle_service,
        "compile_bundle",
        lambda request: (_ for _ in ()).throw(BundleServiceError("simulated rebuild failure")),
    )

    with pytest.raises(MibsError, match="restored"):
        mibs_service.delete_mibs(
            ["ericsson/ERICSSON-A.mib", "ericsson/ERICSSON-B.mib"],
            settings=settings,
            state=state,
            bundle_service=bundle_service,
        )

    assert first_path.exists() is True
    assert second_path.exists() is True


def test_export_catalog_requires_an_active_bundle(isolated_db):
    from app.services import mibs_service
    from app.services.bundle_state import set_bundle
    from app.services.mibs_service import MibsError
    from app.services.state_store import StateStore

    settings = isolated_db["settings"]
    state = StateStore(isolated_db["session_factory"])
    bundle_service = _activate_mibs_bundle(isolated_db)
    set_bundle(None)

    with pytest.raises(MibsError, match="No active MIB bundle"):
        mibs_service.export_catalog(
            settings=settings,
            state=state,
            bundle_service=bundle_service,
        )


def test_export_catalog_filters_and_export_types_cover_live_bundle_exports(isolated_db):
    from app.services import mibs_service
    from app.services.state_store import StateStore

    settings = isolated_db["settings"]
    state = StateStore(isolated_db["session_factory"])
    bundle_service = _activate_mibs_bundle(isolated_db)

    catalog = mibs_service.export_catalog(
        modules=["IF-MIB"],
        notifications=["IF-MIB::linkDown"],
        export_type="catalog",
        settings=settings,
        state=state,
        bundle_service=bundle_service,
    )
    assert catalog["export_version"] == 2
    assert catalog["filters"]["export_type"] == "catalog"
    assert catalog["summary"]["module_count"] == 1
    assert catalog["summary"]["notification_count"] == 1
    assert catalog["notifications"][0]["full_name"] == "IF-MIB::linkDown"
    assert all(item["module"] == "IF-MIB" for item in catalog["objects"])

    objects_only = mibs_service.export_catalog(
        modules=["IF-MIB"],
        export_type="objects",
        settings=settings,
        state=state,
        bundle_service=bundle_service,
    )
    assert objects_only["notifications"] == []
    assert objects_only["summary"]["object_count"] >= 1

    modules_only = mibs_service.export_catalog(
        modules=["IF-MIB"],
        export_type="modules",
        settings=settings,
        state=state,
        bundle_service=bundle_service,
    )
    assert modules_only["objects"] == []
    assert modules_only["notifications"] == []
    assert modules_only["summary"]["module_count"] == 1

    summary_only = mibs_service.export_catalog(
        modules=["IF-MIB"],
        export_type="summary",
        settings=settings,
        state=state,
        bundle_service=bundle_service,
    )
    assert summary_only["objects"] == []
    assert summary_only["notifications"] == []
    assert summary_only["summary"]["module_count"] == 1


def test_export_catalog_file_supports_json_and_csv_formats(isolated_db):
    from app.services import mibs_service
    from app.services.mibs_service import MibsError
    from app.services.state_store import StateStore

    settings = isolated_db["settings"]
    state = StateStore(isolated_db["session_factory"])
    bundle_service = _activate_mibs_bundle(isolated_db)

    json_file = mibs_service.export_catalog_file(
        format="json",
        notifications=["IF-MIB::linkDown"],
        export_type="notifications",
        settings=settings,
        state=state,
        bundle_service=bundle_service,
    )
    assert json_file["filename"] == "notifications.json"
    assert json_file["media_type"] == "application/json"
    json_payload = json.loads(json_file["content"].decode("utf-8"))
    assert json_payload["notifications"][0]["full_name"] == "IF-MIB::linkDown"

    csv_notifications = mibs_service.export_catalog_file(
        format="csv",
        notifications=["IF-MIB::linkDown"],
        export_type="notifications",
        settings=settings,
        state=state,
        bundle_service=bundle_service,
    )
    assert csv_notifications["filename"] == "notifications.csv"
    assert csv_notifications["media_type"] == "text/csv"
    csv_notifications_text = csv_notifications["content"].decode("utf-8")
    assert csv_notifications_text.splitlines()[0] == "module,name,oid,description"
    assert "IF-MIB,linkDown,1.3.6.1.6.3.1.1.5.3" in csv_notifications_text

    csv_objects = mibs_service.export_catalog_file(
        format="csv",
        modules=["IF-MIB"],
        export_type="objects",
        settings=settings,
        state=state,
        bundle_service=bundle_service,
    )
    assert csv_objects["filename"] == "objects.csv"
    assert csv_objects["content"].decode("utf-8").splitlines()[0] == "module,name,oid,type"

    with pytest.raises(MibsError, match="Unsupported catalog export format"):
        mibs_service.export_catalog_file(
            format="xml",
            settings=settings,
            state=state,
            bundle_service=bundle_service,
        )
