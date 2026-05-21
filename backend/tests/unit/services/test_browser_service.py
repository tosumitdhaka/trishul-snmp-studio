from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def _activate_browser_bundle(isolated_db):
    from app.services.bundle_state import get_bundle
    from app.services.bundles import BundleCompileRequest, BundleService

    settings = isolated_db["settings"]
    BundleService(settings).compile_bundle(
        BundleCompileRequest(mib_names=["IF-MIB", "SNMPv2-MIB"], activate=True)
    )

    bundle = get_bundle()
    assert bundle is not None
    return bundle


def test_search_treats_blank_filters_as_unset(isolated_db):
    from app.services import browser_service

    bundle = _activate_browser_bundle(isolated_db)

    payload = browser_service.search_bundle(
        query="ifDescr",
        module="",
        type_filter="",
        limit=10,
        bundle=bundle,
    )

    assert payload["count"] >= 1
    assert any(result["name"] == "ifDescr" for result in payload["results"])


def test_node_notification_members_keep_enum_metadata(isolated_db):
    from app.services import browser_service

    bundle = _activate_browser_bundle(isolated_db)

    payload = browser_service.get_node("IF-MIB::linkDown", module=None, bundle=bundle)

    enum_member = next(
        (item for item in payload["trap_objects"] if item["full_name"] == "IF-MIB::ifAdminStatus"),
        None,
    )
    assert enum_member is not None
    assert enum_member["input_type"] == "Integer"
    assert enum_member["syntax"] == "INTEGER"
    assert enum_member["enum_values"] == [
        {"label": "up", "value": 1},
        {"label": "down", "value": 2},
        {"label": "testing", "value": 3},
    ]


def test_resolve_and_search_cover_symbolic_numeric_and_type_filtered_paths(isolated_db):
    from app.services import browser_service

    bundle = _activate_browser_bundle(isolated_db)

    symbolic = browser_service.resolve("IF-MIB::ifDescr", bundle=bundle)
    assert symbolic["resolved"] is True
    assert symbolic["output"].startswith("1.3.6.1.2.1.2.2.1.2")

    numeric = browser_service.resolve(symbolic["output"], mode="symbolic", bundle=bundle)
    assert numeric == {
        "input": symbolic["output"],
        "output": "IF-MIB::ifDescr",
        "resolved": True,
    }

    fallback = browser_service.resolve("ifDescr", mode="symbolic", bundle=bundle)
    assert fallback["output"] == "IF-MIB::ifDescr"

    filtered = browser_service.search_bundle(
        query="if",
        module="IF-MIB",
        type_filter="MibTableColumn",
        limit=25,
        bundle=bundle,
    )
    assert filtered["count"] >= 1
    assert all(result["type"] == "MibTableColumn" for result in filtered["results"])

    assert browser_service.resolve("DEFINITELY-NOT-A-MIB-SYMBOL", bundle=bundle) == {
        "input": "DEFINITELY-NOT-A-MIB-SYMBOL",
        "output": "DEFINITELY-NOT-A-MIB-SYMBOL",
        "resolved": False,
    }


def test_module_tree_oid_tree_and_node_breadcrumbs_cover_browser_navigation(isolated_db):
    from app.services import browser_service

    bundle = _activate_browser_bundle(isolated_db)

    modules = browser_service.get_modules(bundle=bundle)["modules"]
    assert modules == sorted(modules, key=lambda item: item["name"])
    if_mib = next(item for item in modules if item["name"] == "IF-MIB")
    assert if_mib["objects"] >= 1
    assert if_mib["notifications"] >= 1

    module_tree = browser_service.get_module_tree(
        module="IF-MIB",
        type_filter=None,
        bundle=bundle,
    )
    assert module_tree["count"] >= 1
    assert any(child["has_children"] for child in module_tree["modules"][0]["children"])

    oid_tree = browser_service.get_oid_tree(
        root_oid="1.3.6.1.2.1.2.2.1",
        depth=1,
        module="IF-MIB",
        type_filter="MibTableColumn",
        bundle=bundle,
    )
    assert oid_tree["root"]["full_name"] == "IF-MIB::ifEntry"
    assert "ifDescr" in {item["name"] for item in oid_tree["children"]}
    assert all(item["type"] == "MibTableColumn" for item in oid_tree["children"])
    assert oid_tree["total_descendants"] >= len(oid_tree["children"])

    node = browser_service.get_node("1.3.6.1.2.1.2.2.1.2", module=None, bundle=bundle)
    assert node["node"]["full_name"] == "IF-MIB::ifDescr"
    assert any(item["name"] == "ifEntry" for item in node["breadcrumb"])

    assert browser_service.get_oid_tree(
        root_oid="not-an-oid",
        depth=1,
        module=None,
        type_filter=None,
        bundle=bundle,
    ) == {"root": None, "children": [], "total_descendants": 0}


def test_input_type_mapping_and_trap_catalog_cover_trap_sender_metadata(isolated_db):
    from app.services import browser_service
    from app.services.browser_service import _input_type_for_syntax

    bundle = _activate_browser_bundle(isolated_db)

    assert _input_type_for_syntax("OBJECT IDENTIFIER") == "OID"
    assert _input_type_for_syntax("IpAddress") == "IpAddress"
    assert _input_type_for_syntax("TimeTicks") == "TimeTicks"
    assert _input_type_for_syntax("Counter64") == "Counter"
    assert _input_type_for_syntax("Gauge32") == "Gauge"
    assert _input_type_for_syntax("TruthValue") == "Integer"
    assert _input_type_for_syntax("DisplayString") == "String"

    catalog = browser_service.get_trap_catalog(bundle=bundle)
    link_down = next(item for item in catalog["traps"] if item["full_name"] == "IF-MIB::linkDown")
    enum_member = next(item for item in link_down["objects"] if item["full_name"] == "IF-MIB::ifAdminStatus")

    assert link_down["oid"] == "1.3.6.1.6.3.1.1.5.3"
    assert enum_member["input_type"] == "Integer"
    assert enum_member["enum_values"][0] == {"label": "up", "value": 1}
