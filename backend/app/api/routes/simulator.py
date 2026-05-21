from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Header, HTTPException
from pydantic import BaseModel, Field

from app.services import simulator_service
from app.services.session import SessionService, SessionServiceError
from app.services.simulator_service import SimulatorError
from app.services.state_store import get_state_store

router = APIRouter()


class SimulatorStartBody(BaseModel):
    port: int = Field(1061, ge=1, le=65535)
    community: str = Field("public", min_length=1)


def _require_auth(token: str | None) -> None:
    try:
        SessionService().require_username(token)
    except SessionServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


def _sim_http(exc: SimulatorError):
    raise HTTPException(status_code=400, detail=str(exc)) from exc


def _ctx():
    from app.core.config import get_settings
    from app.services.runtime import get_runtime_service
    return get_settings(), get_state_store(), get_runtime_service()


@router.get("/simulator/data")
def get_simulator_data(
    x_auth_token: str | None = Header(default=None),
) -> dict[str, Any]:
    _require_auth(x_auth_token)
    from app.core.config import get_settings
    return simulator_service.get_custom_data(settings=get_settings())


@router.post("/simulator/data")
async def save_simulator_data(
    body: Any = Body(...),
    x_auth_token: str | None = Header(default=None),
) -> dict[str, Any]:
    _require_auth(x_auth_token)
    settings, _state, rt = _ctx()
    try:
        return await simulator_service.save_custom_data(body, settings=settings, runtime_service=rt)
    except SimulatorError as exc:
        _sim_http(exc)


@router.get("/simulator/logs")
async def get_simulator_logs(
    limit: int = 200,
    x_auth_token: str | None = Header(default=None),
) -> dict[str, Any]:
    _require_auth(x_auth_token)
    _s, _st, rt = _ctx()
    try:
        return await simulator_service.get_logs(limit=limit, runtime_service=rt)
    except SimulatorError as exc:
        _sim_http(exc)


@router.delete("/simulator/logs")
async def clear_simulator_logs(
    x_auth_token: str | None = Header(default=None),
) -> dict[str, Any]:
    _require_auth(x_auth_token)
    _s, _st, rt = _ctx()
    try:
        return await simulator_service.clear_logs(runtime_service=rt)
    except SimulatorError as exc:
        _sim_http(exc)


@router.post("/simulator/start")
async def start_simulator(
    body: SimulatorStartBody,
    x_auth_token: str | None = Header(default=None),
) -> dict[str, Any]:
    _require_auth(x_auth_token)
    settings, state, rt = _ctx()
    try:
        return await simulator_service.start(
            port=body.port, community=body.community,
            settings=settings, state=state, runtime_service=rt,
        )
    except SimulatorError as exc:
        _sim_http(exc)


@router.post("/simulator/stop")
async def stop_simulator(
    x_auth_token: str | None = Header(default=None),
) -> dict[str, Any]:
    _require_auth(x_auth_token)
    settings, state, rt = _ctx()
    try:
        return await simulator_service.stop(settings=settings, state=state, runtime_service=rt)
    except SimulatorError as exc:
        _sim_http(exc)


@router.post("/simulator/restart")
async def restart_simulator(
    x_auth_token: str | None = Header(default=None),
) -> dict[str, Any]:
    _require_auth(x_auth_token)
    settings, state, rt = _ctx()
    try:
        return await simulator_service.restart(settings=settings, state=state, runtime_service=rt)
    except SimulatorError as exc:
        _sim_http(exc)


@router.get("/simulator/status")
async def get_simulator_status(
    x_auth_token: str | None = Header(default=None),
) -> dict[str, Any]:
    _require_auth(x_auth_token)
    _s, state, rt = _ctx()
    return await simulator_service.get_status(state=state, runtime_service=rt)
