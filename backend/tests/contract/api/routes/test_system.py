from __future__ import annotations

from datetime import datetime

import pytest

pytestmark = pytest.mark.contract


def test_system_routes_return_current_metadata_and_health(isolated_db):
    from app.api.routes import system as system_module

    settings = isolated_db["settings"]

    assert system_module.get_meta() == {
        "name": settings.app_name,
        "version": settings.app_version,
        "author": settings.app_author,
        "description": settings.app_description,
    }

    health = system_module.get_health()
    assert health["status"] == "ok"
    assert health["service"] == settings.app_name
    assert health["version"] == settings.app_version
    datetime.fromisoformat(health["time"])
