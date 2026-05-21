from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select

pytestmark = pytest.mark.unit


def test_compile_bundle_creates_storage_and_compile_run(isolated_db):
    from app.models import BundleSet, CompileRun
    from app.services.bundles import BundleCompileRequest, BundleService

    service = BundleService(isolated_db["settings"])
    result = service.compile_bundle(BundleCompileRequest(mib_names=["SNMPv2-MIB"]))

    bundle = result["bundle"]
    compile_run = result["compile_run"]

    assert bundle["bundle_key"].startswith("run-")
    assert bundle["status"] == "compiled"
    assert bundle["is_active"] is False
    assert Path(bundle["storage_path"]).is_dir()
    assert Path(bundle["manifest_path"]).exists()
    assert Path(bundle["oid_index_path"]).exists()
    assert bundle["module_count"] >= 1
    assert any(module["module_name"] == "SNMPv2-MIB" for module in bundle["modules"])
    assert compile_run["status"] == "succeeded"
    assert compile_run["bundle_set_id"] == bundle["id"]

    with isolated_db["session_factory"]() as session:
        stored_bundle = session.scalar(select(BundleSet).where(BundleSet.id == bundle["id"]))
        stored_compile_run = session.scalar(
            select(CompileRun).where(CompileRun.id == compile_run["id"])
        )

        assert stored_bundle is not None
        assert stored_compile_run is not None
        assert stored_compile_run.bundle_set_id == stored_bundle.id
        assert stored_compile_run.output_dir == stored_bundle.storage_path


def test_compile_bundle_stores_metadata_not_subprocess_command(isolated_db):
    from app.services.bundles import BundleCompileRequest, BundleService

    settings = isolated_db["settings"]
    service = BundleService(settings)
    result = service.compile_bundle(BundleCompileRequest(mib_names=["SNMPv2-MIB"]))

    detail = service.get_bundle(result["bundle"]["id"])
    command = detail["compile_runs"][0]["command"]
    assert isinstance(command, dict)
    assert "mib_names" in command
    assert "SNMPv2-MIB" in command["mib_names"]


def test_activate_and_rollback_switch_active_bundle_pointer(isolated_db):
    from app.services.bundles import BundleCompileRequest, BundleService

    service = BundleService(isolated_db["settings"])

    first_result = service.compile_bundle(BundleCompileRequest(mib_names=["SNMPv2-MIB"]))
    first_bundle_id = first_result["bundle"]["id"]
    first_activation = service.activate_bundle(first_bundle_id)

    assert first_activation["active_bundle_id"] == first_bundle_id
    assert first_activation["previous_active_bundle_id"] is None
    assert first_activation["bundle"]["is_active"] is True

    second_result = service.compile_bundle(BundleCompileRequest(mib_names=["IF-MIB"]))
    second_bundle_id = second_result["bundle"]["id"]
    second_activation = service.activate_bundle(second_bundle_id)

    assert second_activation["active_bundle_id"] == second_bundle_id
    assert second_activation["previous_active_bundle_id"] == first_bundle_id
    assert second_activation["bundle"]["is_active"] is True
    pointer_after_second = service.read_active_pointer()
    assert pointer_after_second is not None
    assert pointer_after_second["bundle_set_id"] == second_bundle_id
    assert pointer_after_second["previous_active_bundle_id"] == first_bundle_id

    rollback = service.rollback_bundle()

    assert rollback["active_bundle_id"] == first_bundle_id
    assert rollback["previous_active_bundle_id"] == second_bundle_id
    pointer_after_rollback = service.read_active_pointer()
    assert pointer_after_rollback is not None
    assert pointer_after_rollback["bundle_set_id"] == first_bundle_id
    assert pointer_after_rollback["previous_active_bundle_id"] == second_bundle_id

    state = service.list_state()
    bundles_by_id = {bundle["id"]: bundle for bundle in state["bundles"]}
    assert bundles_by_id[first_bundle_id]["is_active"] is True
    assert bundles_by_id[first_bundle_id]["status"] == "active"
    assert bundles_by_id[second_bundle_id]["is_active"] is False
    assert bundles_by_id[second_bundle_id]["status"] == "compiled"
    assert state["active_bundle_id"] == first_bundle_id
    assert state["previous_active_bundle_id"] == second_bundle_id
    assert state["active_pointer"]["bundle_set_id"] == first_bundle_id


def test_bundle_detail_and_diff_service_expose_dependency_and_change_data(isolated_db):
    from app.services.bundles import BundleCompileRequest, BundleService

    service = BundleService(isolated_db["settings"])
    first_result = service.compile_bundle(BundleCompileRequest(mib_names=["SNMPv2-MIB"]))
    second_result = service.compile_bundle(
        BundleCompileRequest(mib_names=["SNMPv2-MIB", "IF-MIB"])
    )

    detail = service.get_bundle(second_result["bundle"]["id"])
    assert detail["bundle"]["id"] == second_result["bundle"]["id"]
    assert "IF-MIB" in detail["manifest"]["modules"]
    assert detail["compile_runs"][0]["bundle_set_id"] == second_result["bundle"]["id"]

    dependency_nodes = {
        node["module_name"]: node for node in detail["dependency_graph"]["nodes"]
    }
    assert "IF-MIB" in dependency_nodes
    assert any(
        edge["target"] == "SNMPv2-MIB"
        for edge in dependency_nodes["IF-MIB"]["imports"]
    )
    assert "SNMPv2-SMI" in detail["dependency_graph"]["external_dependencies"]

    diff = service.diff_bundles(
        first_result["bundle"]["id"],
        second_result["bundle"]["id"],
    )
    added_modules = {item["module_name"] for item in diff["modules_added"]}
    assert "IF-MIB" in added_modules
    assert diff["summary"]["modules"]["added"] >= 1
    assert (
        diff["summary"]["objects"]["right_total"]
        >= diff["summary"]["objects"]["left_total"]
    )


def test_ensure_bootstrap_bundle_compiles_and_activates_bundled_sources(isolated_db):
    from app.services.bundles import BUNDLED_STARTER_MIBS, BundleService

    service = BundleService(isolated_db["settings"])
    bundle = service.ensure_bootstrap_bundle()

    assert bundle is not None
    assert bundle["is_active"] is True
    assert bundle["status"] == "active"
    assert {module["module_name"] for module in bundle["modules"]} == set(
        BUNDLED_STARTER_MIBS
    )

    state = service.list_state()
    assert state["active_bundle_id"] == bundle["id"]
    assert state["active_pointer"] is not None
    assert state["active_pointer"]["bundle_set_id"] == bundle["id"]
