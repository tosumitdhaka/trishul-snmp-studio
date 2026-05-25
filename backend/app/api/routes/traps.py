from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from app.services import traps_service
from app.services.history import EventHistoryService
from app.services.realtime import broadcast_stats, broadcast_status
from app.services.session import SessionService, SessionServiceError
from app.services.state_store import get_state_store
from app.services.traps_service import TrapsError

router = APIRouter()


class TrapListenerBody(BaseModel):
    port: int = Field(1162, ge=1, le=65535)
    community: str = Field("public", min_length=1)
    resolve_mibs: bool = True


class TrapResolveMibsBody(BaseModel):
    resolve_mibs: bool


class TrapVarBindBody(BaseModel):
    oid: str = Field(..., min_length=1)
    type: str = Field(..., min_length=1)
    value: Any | None = None


class TrapSendBody(BaseModel):
    target: str = Field(..., min_length=1)
    port: int = Field(1162, ge=1, le=65535)
    community: str = Field("public", min_length=1)
    oid: str = Field(..., min_length=1)
    varbinds: list[TrapVarBindBody] = Field(default_factory=list)


def _require_auth(token: str | None) -> None:
    try:
        SessionService().require_username(token)
    except SessionServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


def _traps_http(exc: TrapsError):
    raise HTTPException(status_code=400, detail=str(exc)) from exc


def _ctx():
    from app.core.config import get_settings
    from app.services.runtime import get_runtime_service
    return get_settings(), get_state_store(), get_runtime_service()


@router.get("/traps/status")
async def get_trap_status(
    x_auth_token: str | None = Header(default=None),
) -> dict[str, Any]:
    _require_auth(x_auth_token)
    _s, state, rt = _ctx()
    return await traps_service.get_status(state=state, runtime_service=rt)


@router.post("/traps/start")
async def start_trap_listener(
    body: TrapListenerBody,
    x_auth_token: str | None = Header(default=None),
) -> dict[str, Any]:
    _require_auth(x_auth_token)
    settings, state, rt = _ctx()
    try:
        return await traps_service.start_listener(
            port=body.port, community=body.community, resolve_mibs=body.resolve_mibs,
            settings=settings, state=state, runtime_service=rt,
        )
    except TrapsError as exc:
        _traps_http(exc)


@router.post("/traps/stop")
async def stop_trap_listener(
    x_auth_token: str | None = Header(default=None),
) -> dict[str, Any]:
    _require_auth(x_auth_token)
    settings, state, rt = _ctx()
    try:
        return await traps_service.stop_listener(settings=settings, state=state, runtime_service=rt)
    except TrapsError as exc:
        _traps_http(exc)


@router.post("/traps/send")
async def send_trap(
    body: TrapSendBody,
    x_auth_token: str | None = Header(default=None),
) -> dict[str, Any]:
    _require_auth(x_auth_token)
    settings, _state, rt = _ctx()
    try:
        return await traps_service.send_trap(
            target=body.target,
            port=body.port,
            community=body.community,
            oid=body.oid,
            varbinds=[item.model_dump() for item in body.varbinds],
            settings=settings,
            runtime_service=rt,
        )
    except TrapsError as exc:
        _traps_http(exc)


@router.post("/traps/resolve-mibs")
async def set_resolve_mibs(
    body: TrapResolveMibsBody,
    x_auth_token: str | None = Header(default=None),
) -> dict[str, Any]:
    """Update resolve_mibs preference live — no receiver restart needed."""
    _require_auth(x_auth_token)
    from app.services.state_store import _TRAP_RESOLVE_MIBS_KEY
    settings, state, _rt = _ctx()
    state.set_value(_TRAP_RESOLVE_MIBS_KEY, bool(body.resolve_mibs))
    await broadcast_status(settings=settings)
    return {"resolve_mibs": bool(body.resolve_mibs)}


@router.get("/traps")
@router.get("/traps/")
def list_traps(
    x_auth_token: str | None = Header(default=None),
) -> dict[str, Any]:
    _require_auth(x_auth_token)
    from app.core.config import get_settings
    return traps_service.list_events(
        state=get_state_store(),
        history_service=EventHistoryService(get_settings()),
    )


@router.delete("/traps")
@router.delete("/traps/")
async def clear_traps(
    x_auth_token: str | None = Header(default=None),
) -> dict[str, str]:
    _require_auth(x_auth_token)
    from app.core.config import get_settings
    result = traps_service.clear_events(history_service=EventHistoryService(get_settings()))
    await broadcast_stats(settings=get_settings())
    return result
