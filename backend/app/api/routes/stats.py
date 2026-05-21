from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException

from app.services import stats_service
from app.services.history import EventHistoryService
from app.services.realtime import broadcast_stats
from app.services.session import SessionService, SessionServiceError
from app.services.state_store import get_state_store

router = APIRouter()


def _require_auth(token: str | None) -> None:
    try:
        SessionService().require_username(token)
    except SessionServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get("/stats")
@router.get("/stats/")
async def get_stats(
    x_auth_token: str | None = Header(default=None),
) -> dict[str, Any]:
    _require_auth(x_auth_token)
    from app.core.config import get_settings
    from app.services.runtime import get_runtime_service
    settings = get_settings()
    return await stats_service.get_stats(
        state=get_state_store(),
        history_service=EventHistoryService(settings),
        runtime_service=get_runtime_service(),
        settings=settings,
    )


@router.delete("/stats")
@router.delete("/stats/")
async def reset_stats(
    x_auth_token: str | None = Header(default=None),
) -> dict[str, str]:
    _require_auth(x_auth_token)
    from app.core.config import get_settings
    from app.services.runtime import get_runtime_service
    settings = get_settings()
    result = await stats_service.reset_stats(
        state=get_state_store(),
        history_service=EventHistoryService(settings),
        runtime_service=get_runtime_service(),
    )
    await broadcast_stats(settings=settings)
    return result
