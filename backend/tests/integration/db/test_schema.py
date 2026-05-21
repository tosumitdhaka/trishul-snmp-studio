from __future__ import annotations

import pytest
from sqlalchemy import select

pytestmark = pytest.mark.integration


def test_isolated_db_supports_schema_writes(isolated_db, tmp_path):
    from app.models import AppSetting, AuthSession, BundleModule, BundleSet

    session_factory = isolated_db["session_factory"]

    with session_factory() as session:
        session.add(AppSetting(key="ui.theme", value_json={"name": "sunrise"}))
        session.add(AuthSession(token="session-1", username="admin"))

        bundle_set = BundleSet(
            bundle_key="starter-bundle",
            label="Starter Bundle",
            storage_path=str(tmp_path / "bundles" / "starter-bundle"),
            manifest_path=str(tmp_path / "bundles" / "starter-bundle" / "manifest.json"),
            oid_index_path=str(tmp_path / "bundles" / "starter-bundle" / "oid_index.json"),
        )
        bundle_set.modules.append(
            BundleModule(
                module_name="SNMPv2-MIB",
                source_path=str(tmp_path / "mibs" / "SNMPv2-MIB.mib"),
                compiled_path=str(
                    tmp_path / "bundles" / "starter-bundle" / "SNMPv2-MIB.json"
                ),
                module_identity_oid="1.3.6.1.6.3.1.1",
                object_count=42,
                notification_count=7,
            )
        )
        session.add(bundle_set)
        session.commit()

    with session_factory() as session:
        stored_setting = session.get(AppSetting, "ui.theme")
        stored_auth_session = session.get(AuthSession, "session-1")
        stored_bundle = session.scalar(
            select(BundleSet).where(BundleSet.bundle_key == "starter-bundle")
        )

        assert stored_setting is not None
        assert stored_setting.value_json == {"name": "sunrise"}
        assert stored_auth_session is not None
        assert stored_auth_session.username == "admin"
        assert stored_bundle is not None
        assert stored_bundle.storage_path.endswith("starter-bundle")
        assert len(stored_bundle.modules) == 1
        assert stored_bundle.modules[0].module_name == "SNMPv2-MIB"
        assert stored_bundle.modules[0].notification_count == 7
