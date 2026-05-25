from __future__ import annotations

import anyio
import logging
import pytest
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request

pytestmark = pytest.mark.unit


def test_create_app_mounts_frontend_dist_when_present(monkeypatch, tmp_path):
    from app.core.config import reset_settings_cache
    from app.db.session import reset_db_runtime
    from app.main import SPAStaticFiles, create_app

    data_dir = tmp_path / "app-data"
    frontend_dir = tmp_path / "frontend-dist"
    frontend_dir.mkdir(parents=True, exist_ok=True)
    (frontend_dir / "index.html").write_text("<!doctype html><title>suite</title><main>ok</main>")

    monkeypatch.setenv("TRISHUL_DATA_DIR", str(data_dir))
    monkeypatch.setenv("TRISHUL_FRONTEND_DIST", str(frontend_dir))

    reset_settings_cache()
    reset_db_runtime()

    app = create_app()
    mounted = next(route for route in app.routes if getattr(route, "name", None) == "frontend")
    assert isinstance(mounted.app, SPAStaticFiles)
    calls: list[str] = []

    async def fake_get_response(self, path, scope):
        del self
        calls.append(path)
        if path == "index.html":
            return Response("mounted-fallback", media_type="text/html")
        return Response(status_code=404)

    monkeypatch.setattr(StaticFiles, "get_response", fake_get_response)

    async def render_unknown_path() -> tuple[int, str | None]:
        response = await mounted.app.get_response(
            "missing/view",
            {"method": "GET", "path": "/missing/view", "headers": []},
        )
        return response.status_code, response.body.decode("utf-8")

    status_code, response_body = anyio.run(render_unknown_path)
    assert status_code == 200
    assert response_body == "mounted-fallback"
    assert calls == ["missing/view", "index.html"]

    reset_db_runtime()
    reset_settings_cache()


def test_create_app_exposes_placeholder_and_base_metadata_when_frontend_missing(
    monkeypatch,
    tmp_path,
):
    from app.core.config import get_settings, reset_settings_cache
    from app.db.base import Base
    from app.db.session import reset_db_runtime
    from app.main import create_app

    data_dir = tmp_path / "app-data"
    frontend_dir = tmp_path / "missing-dist"

    monkeypatch.setenv("TRISHUL_DATA_DIR", str(data_dir))
    monkeypatch.setenv("TRISHUL_FRONTEND_DIST", str(frontend_dir))

    reset_settings_cache()
    reset_db_runtime()

    settings = get_settings()
    assert settings.frontend_dist_dir == frontend_dir.resolve()
    assert settings.bundle_pointer_file.name == "active_bundle.json"
    assert Base.metadata is not None

    app = create_app()
    placeholder_route = next(
        route
        for route in app.routes
        if getattr(route, "path", None) == "/"
        and getattr(route, "name", "") == "frontend_placeholder"
    )
    response = placeholder_route.endpoint()
    assert "Frontend build not found." in response.body.decode("utf-8")
    assert "npm run build" in response.body.decode("utf-8")

    reset_db_runtime()
    reset_settings_cache()


def test_spa_static_files_uses_index_when_static_lookup_raises_404(monkeypatch, tmp_path):
    from app.main import SPAStaticFiles

    frontend_dir = tmp_path / "frontend-dist"
    frontend_dir.mkdir(parents=True, exist_ok=True)

    app = SPAStaticFiles(directory=str(frontend_dir), html=True)
    calls: list[str] = []

    async def fake_get_response(self, path, scope):
        del self
        calls.append(path)
        if path == "index.html":
            return Response("fallback", media_type="text/html")
        raise StarletteHTTPException(status_code=404)

    monkeypatch.setattr(StaticFiles, "get_response", fake_get_response)

    async def render_unknown_path():
        return await app.get_response(
            "missing/view",
            {"method": "GET", "path": "/missing/view", "headers": []},
        )

    response = anyio.run(render_unknown_path)
    assert response.status_code == 200
    assert calls == ["missing/view", "index.html"]


def test_create_app_logs_only_debug_or_error_http_requests(isolated_db, monkeypatch):
    import app.main as main_module

    emitted: list[tuple[str | int, str, str]] = []
    exceptions: list[str] = []

    monkeypatch.setattr(
        main_module,
        "emit_backend_log",
        lambda message, *, level="INFO", logger_name="app", settings=None: emitted.append(
            (level, logger_name, message)
        ),
    )
    monkeypatch.setattr(
        main_module.logger,
        "exception",
        lambda message: exceptions.append(message),
    )

    monkeypatch.setattr(main_module, "get_settings", lambda: isolated_db["settings"])
    app = main_module.create_app()
    dispatch = app.user_middleware[0].kwargs["dispatch"]

    def make_request(path: str) -> Request:
        return Request(
            {
                "type": "http",
                "http_version": "1.1",
                "scheme": "http",
                "method": "GET",
                "path": path,
                "raw_path": path.encode("utf-8"),
                "query_string": b"",
                "headers": [],
                "client": ("127.0.0.1", 50000),
                "server": ("testserver", 80),
            }
        )

    async def ok_call_next(_request: Request) -> Response:
        return Response("ok", status_code=200)

    async def warn_call_next(_request: Request) -> Response:
        return Response("warn", status_code=401)

    async def error_call_next(_request: Request) -> Response:
        raise RuntimeError("boom")

    anyio.run(lambda: dispatch(make_request("/api/meta"), ok_call_next))
    assert emitted == []

    emitted.clear()
    anyio.run(lambda: dispatch(make_request("/api/simulator/logs"), ok_call_next))
    assert emitted == []

    anyio.run(lambda: dispatch(make_request("/api/settings/check"), warn_call_next))
    assert emitted[-1][0] == logging.WARNING
    assert emitted[-1][1] == "app.http"
    assert emitted[-1][2].startswith("HTTP GET /api/settings/check -> 401")

    emitted.clear()
    isolated_db["settings"].log_level = "DEBUG"
    anyio.run(lambda: dispatch(make_request("/api/meta"), ok_call_next))
    assert emitted[-1][0] == logging.DEBUG
    assert emitted[-1][1] == "app.http"
    assert emitted[-1][2].startswith("HTTP GET /api/meta -> 200")

    try:
        anyio.run(lambda: dispatch(make_request("/api/healthz/ui"), error_call_next))
    except RuntimeError:
        pass
    else:
        raise AssertionError("middleware should re-raise unexpected request errors")

    assert exceptions
    assert exceptions[-1].startswith("HTTP GET /api/healthz/ui failed after ")
