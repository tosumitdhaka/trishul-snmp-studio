from __future__ import annotations

import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy import text

from app.api.router import router as api_router
from app.core.config import get_settings
from app.core.logging import configure_logging, emit_backend_log
from app.db.migrations import upgrade_database
from app.db.session import get_engine
from app.services.bundle_state import set_bundle
from app.services.bundles import BundleService, BundleServiceError
from app.services.state_store import init_state_store
from app.services.runtime import shutdown_runtime_service


class SPAStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):  # type: ignore[override]
        try:
            response = await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404 and scope["method"] == "GET":
                return await super().get_response("index.html", scope)
            raise
        if response.status_code == 404 and scope["method"] == "GET":
            return await super().get_response("index.html", scope)
        return response


configure_logging(get_settings())
logger = logging.getLogger(__name__)

_QUIET_GET_API_PATHS = {
    "/api/simulator/logs",
    "/api/simulator/status",
    "/api/traps/",
    "/api/traps/status",
}


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    configure_logging(settings)
    from app.db.session import create_session_factory
    init_state_store(create_session_factory(settings.database_url))
    logger.info("Applying database migrations for %s", settings.database_url)
    upgrade_database()
    logger.info("Backend log file is available at %s", settings.log_dir / "backend.log")
    bundle_service = BundleService(settings)
    try:
        bootstrap_bundle = bundle_service.ensure_bootstrap_bundle()
        if bootstrap_bundle is not None:
            logger.info(
                "Effective bundle ready: %s (%s)",
                bootstrap_bundle["bundle_key"],
                bootstrap_bundle["status"],
            )
    except BundleServiceError:
        logger.exception("Failed to prepare the bundled starter MIB set")

    # Load the active bundle into memory for catalog/browser queries
    try:
        from trishul_snmp import load_bundle as _load_bundle
        summary = bundle_service.get_effective_bundle_summary()
        if summary:
            set_bundle(_load_bundle(summary["storage_path"]))
            logger.info("Loaded MIB bundle into memory: %s", summary["bundle_key"])
    except Exception:
        logger.exception("Failed to load active bundle into memory")
    engine = get_engine()
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))

    # Auto-start simulator and trap receiver if configured
    try:
        from app.services import simulator_service, traps_service
        from app.services.runtime import get_runtime_service
        from app.services.state_store import (
            get_state_store, _AUTO_START_SIMULATOR_KEY, _AUTO_START_TRAP_RECEIVER_KEY,
            _SIMULATOR_PORT_KEY, _SIMULATOR_COMMUNITY_KEY,
            _LISTENER_PORT_KEY, _LISTENER_COMMUNITY_KEY, _TRAP_RESOLVE_MIBS_KEY,
        )
        state = get_state_store()
        snap = state.snapshot()
        runtime_service = get_runtime_service()
        if snap.get(_AUTO_START_SIMULATOR_KEY):
            port = state.coerce_port(snap.get(_SIMULATOR_PORT_KEY), default=1061)
            community = state.coerce_community(snap.get(_SIMULATOR_COMMUNITY_KEY), default="public")
            try:
                await simulator_service.start(port=port, community=community, settings=settings, state=state, runtime_service=runtime_service)
            except Exception as exc:
                logger.error("Simulator auto-start failed: %s", exc)
        if snap.get(_AUTO_START_TRAP_RECEIVER_KEY):
            port = state.coerce_port(snap.get(_LISTENER_PORT_KEY), default=1162)
            community = state.coerce_community(snap.get(_LISTENER_COMMUNITY_KEY), default="public")
            resolve_mibs = bool(snap.get(_TRAP_RESOLVE_MIBS_KEY, True))
            try:
                await traps_service.start_listener(port=port, community=community, resolve_mibs=resolve_mibs, settings=settings, state=state, runtime_service=runtime_service)
            except Exception as exc:
                logger.error("Trap receiver auto-start failed: %s", exc)
    except Exception as exc:
        logger.exception("Failed to check autostart settings: %s", exc)

    yield

    await shutdown_runtime_service()
    engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
    )

    allowed_origins = [
        origin.strip()
        for origin in os.getenv(
            "ALLOWED_ORIGINS",
            "http://localhost:8080,http://localhost:8000,http://localhost:5173",
        ).split(",")
        if origin.strip()
    ]

    application.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.middleware("http")
    async def request_logging_middleware(request: Request, call_next):
        started_at = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            elapsed_ms = (time.perf_counter() - started_at) * 1000
            message = (
                f"HTTP {request.method} {request.url.path} failed after {elapsed_ms:.2f}ms "
                f"from {request.client.host if request.client is not None else '-'}"
            )
            emit_backend_log(message, level="ERROR", logger_name="app.http", settings=settings)
            logger.exception(
                message
            )
            raise

        elapsed_ms = (time.perf_counter() - started_at) * 1000
        quiet_poll = request.method == "GET" and request.url.path in _QUIET_GET_API_PATHS
        if (request.url.path.startswith("/api") and not quiet_poll) or response.status_code >= 400:
            level = logging.INFO
            if response.status_code >= 500:
                level = logging.ERROR
            elif response.status_code >= 400:
                level = logging.WARNING
            message = (
                f"HTTP {request.method} {request.url.path} -> {response.status_code} "
                f"in {elapsed_ms:.2f}ms from {request.client.host if request.client is not None else '-'}"
            )
            emit_backend_log(
                message,
                level=logging.getLevelName(level),
                logger_name="app.http",
                settings=settings,
            )
            logger.log(
                level,
                message,
            )
        return response

    application.include_router(api_router)

    if settings.frontend_dist_dir.exists():
        application.mount(
            "/",
            SPAStaticFiles(directory=str(settings.frontend_dist_dir), html=True),
            name="frontend",
        )
    else:
        @application.get("/", include_in_schema=False)
        def frontend_placeholder() -> HTMLResponse:
            return HTMLResponse(
                """
                <!doctype html>
                <html lang="en">
                  <head>
                    <meta charset="utf-8" />
                    <meta name="viewport" content="width=device-width, initial-scale=1" />
                    <title>Trishul SNMP Suite 2.0.0</title>
                    <style>
                      body {
                        font-family: "Trebuchet MS", "Segoe UI", sans-serif;
                        margin: 0;
                        min-height: 100vh;
                        display: grid;
                        place-items: center;
                        background: linear-gradient(135deg, #f7f2e8, #edf6f3);
                        color: #123239;
                      }
                      main {
                        max-width: 42rem;
                        padding: 2rem 2.25rem;
                        border-radius: 1.25rem;
                        background: rgba(255, 255, 255, 0.88);
                        box-shadow: 0 1.5rem 3rem rgba(18, 50, 57, 0.08);
                      }
                      code {
                        background: rgba(18, 50, 57, 0.08);
                        padding: 0.2rem 0.4rem;
                        border-radius: 0.4rem;
                      }
                    </style>
                  </head>
                  <body>
                    <main>
                      <p>Trishul SNMP Suite 2.0.0 backend is running.</p>
                      <h1>Frontend build not found.</h1>
                      <p>
                        Run <code>npm install</code> and <code>npm run build</code>
                        inside <code>frontend/</code> to generate the UI artifact.
                      </p>
                    </main>
                  </body>
                </html>
                """
            )

    return application


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
    )
