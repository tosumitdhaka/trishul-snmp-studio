from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from app.services.app_settings import AppSettingsService
from app.services.session import SessionService, SessionServiceError
from app.services.state_store import (
    StateStore,
    _AUTO_START_SIMULATOR_KEY,
    _AUTO_START_TRAP_RECEIVER_KEY,
    _MIB_AUTO_FETCH_KEY,
    _MIB_REMOTE_SOURCES_KEY,
    get_state_store,
)

router = APIRouter()


class LoginBody(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class AuthBody(BaseModel):
    current_password: str = Field(..., min_length=1)
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class SettingsBody(BaseModel):
    auto_start_simulator: bool = False
    auto_start_trap_receiver: bool = False
    session_timeout: int = Field(3600, ge=60, le=86400)
    mib_auto_fetch: bool = False
    mib_remote_sources: list[str] = Field(default_factory=list)


_session_service_factory = SessionService
_app_settings_factory = AppSettingsService


def _session() -> SessionService:
    return _session_service_factory()


def _app_settings() -> AppSettingsService:
    return _app_settings_factory()


def _state() -> StateStore:
    return get_state_store()


def _require_auth(token: str | None) -> str:
    try:
        return _session().require_username(token)
    except SessionServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


def _session_http(exc: SessionServiceError):
    raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/settings/login")
def login(body: LoginBody) -> dict[str, str]:
    try:
        return _session().login(username=body.username, password=body.password)
    except SessionServiceError as exc:
        _session_http(exc)


@router.post("/settings/logout")
def logout(x_auth_token: str | None = Header(default=None)) -> dict[str, str]:
    try:
        return _session().logout(token=x_auth_token)
    except SessionServiceError as exc:
        _session_http(exc)


@router.get("/settings/check")
def check_session(x_auth_token: str | None = Header(default=None)) -> dict[str, str]:
    try:
        return _session().check(token=x_auth_token)
    except SessionServiceError as exc:
        _session_http(exc)


@router.post("/settings/auth")
def update_auth(
    body: AuthBody,
    x_auth_token: str | None = Header(default=None),
) -> dict[str, object]:
    try:
        return _session().update_credentials(
            token=x_auth_token,
            current_password=body.current_password,
            username=body.username,
            password=body.password,
        )
    except SessionServiceError as exc:
        _session_http(exc)


@router.get("/settings/app")
def get_settings_app(
    x_auth_token: str | None = Header(default=None),
) -> dict[str, Any]:
    _require_auth(x_auth_token)
    state = _state()
    app_settings = _app_settings()
    values = app_settings.get_values()
    snap = state.snapshot()
    return {
        "auto_start_simulator": bool(snap[_AUTO_START_SIMULATOR_KEY]),
        "auto_start_trap_receiver": bool(snap[_AUTO_START_TRAP_RECEIVER_KEY]),
        "session_timeout": int(values.get("session_timeout_seconds", 3600)),
        "mib_auto_fetch": bool(snap[_MIB_AUTO_FETCH_KEY]),
        "mib_remote_sources": list(snap[_MIB_REMOTE_SOURCES_KEY]),
    }


@router.post("/settings/app")
def update_settings_app(
    body: SettingsBody,
    x_auth_token: str | None = Header(default=None),
) -> dict[str, Any]:
    _require_auth(x_auth_token)
    state = _state()
    app_settings = _app_settings()
    from app.services.app_settings import AppSettingsServiceError
    try:
        app_settings.update_settings({"session_timeout_seconds": int(body.session_timeout)})
    except AppSettingsServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    state.set_value(_AUTO_START_SIMULATOR_KEY, bool(body.auto_start_simulator))
    state.set_value(_AUTO_START_TRAP_RECEIVER_KEY, bool(body.auto_start_trap_receiver))
    state.set_value(_MIB_AUTO_FETCH_KEY, bool(body.mib_auto_fetch))
    raw_sources = body.mib_remote_sources if isinstance(body.mib_remote_sources, list) else []
    state.set_value(_MIB_REMOTE_SOURCES_KEY, [s.strip() for s in raw_sources if s.strip()])
    return {**get_settings_app(x_auth_token=x_auth_token), "restart_required": False}


@router.get("/healthz/ui")
def shell_health_probe() -> dict[str, Any]:
    return {"status": "ok"}
