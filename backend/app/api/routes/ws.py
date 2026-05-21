from __future__ import annotations

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.realtime import build_full_state, ws_manager
from app.services.session import SessionService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    token = websocket.query_params.get("token")
    session_service = SessionService()
    valid, _username, reason = session_service.validate_token(token, touch=True)
    if not valid:
        await websocket.close(code=4001, reason=reason or "Unauthorized")
        return

    await ws_manager.connect(websocket, token=str(token))

    try:
        await ws_manager.send_to(websocket, await build_full_state())

        while True:
            payload = await websocket.receive_text()
            valid, _username, reason = session_service.validate_token(token, touch=True)
            if not valid:
                await websocket.close(code=4001, reason=reason or "Unauthorized")
                ws_manager.disconnect(websocket)
                break
            if payload == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        logger.exception("Unexpected websocket error")
        ws_manager.disconnect(websocket)
