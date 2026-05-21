from __future__ import annotations

import asyncio

import pytest
from starlette.websockets import WebSocketDisconnect

pytestmark = pytest.mark.contract


def test_websocket_endpoint_pushes_full_state_and_answers_ping(monkeypatch):
    from app.api.routes import ws as ws_module

    class StubSessionService:
        def validate_token(self, token, *, touch=False):
            del token
            del touch
            return True, "admin", None

    class StubManager:
        def __init__(self) -> None:
            self.connected: list[str] = []
            self.payloads: list[dict[str, object]] = []
            self.disconnected: list[object] = []

        async def connect(self, websocket, *, token: str) -> None:
            del websocket
            self.connected.append(token)

        async def send_to(self, websocket, payload) -> None:
            del websocket
            self.payloads.append(payload)

        def disconnect(self, websocket) -> None:
            self.disconnected.append(websocket)

    class DummyWebSocket:
        def __init__(self) -> None:
            self.query_params = {"token": "demo-token"}
            self.sent_text: list[str] = []
            self.receive_calls = 0

        async def receive_text(self) -> str:
            self.receive_calls += 1
            if self.receive_calls == 1:
                return "ping"
            raise WebSocketDisconnect(code=1000)

        async def send_text(self, value: str) -> None:
            self.sent_text.append(value)

    async def fake_build_full_state():
        return {
            "type": "full_state",
            "simulator": {"running": False},
            "traps": {"running": False},
            "stats": {"walker": {"walks_executed": 0}},
        }

    manager = StubManager()
    websocket = DummyWebSocket()

    monkeypatch.setattr(ws_module, "SessionService", StubSessionService)
    monkeypatch.setattr(ws_module, "ws_manager", manager)
    monkeypatch.setattr(ws_module, "build_full_state", fake_build_full_state)

    asyncio.run(ws_module.websocket_endpoint(websocket))

    assert manager.connected == ["demo-token"]
    assert manager.payloads == [
        {
            "type": "full_state",
            "simulator": {"running": False},
            "traps": {"running": False},
            "stats": {"walker": {"walks_executed": 0}},
        }
    ]
    assert websocket.sent_text == ["pong"]
    assert manager.disconnected == [websocket]


def test_websocket_endpoint_rejects_invalid_token(monkeypatch):
    from app.api.routes import ws as ws_module

    class StubSessionService:
        def validate_token(self, token, *, touch=False):
            del token
            del touch
            return False, None, "Unauthorized"

    class DummyWebSocket:
        def __init__(self) -> None:
            self.query_params = {"token": "invalid-token"}
            self.closed: list[tuple[int, str]] = []

        async def close(self, code: int, reason: str = "") -> None:
            self.closed.append((code, reason))

    websocket = DummyWebSocket()
    monkeypatch.setattr(ws_module, "SessionService", StubSessionService)

    asyncio.run(ws_module.websocket_endpoint(websocket))

    assert websocket.closed == [(4001, "Unauthorized")]


def test_websocket_endpoint_disconnects_when_token_expires_after_connect(monkeypatch):
    from app.api.routes import ws as ws_module

    class StubSessionService:
        def __init__(self) -> None:
            self.calls = 0

        def validate_token(self, token, *, touch=False):
            del token
            del touch
            self.calls += 1
            if self.calls == 1:
                return True, "admin", None
            return False, None, "Session expired"

    class StubManager:
        def __init__(self) -> None:
            self.connected: list[str] = []
            self.sent_payloads: list[dict[str, object]] = []
            self.disconnected: list[object] = []

        async def connect(self, websocket, *, token: str) -> None:
            del websocket
            self.connected.append(token)

        async def send_to(self, websocket, payload):
            del websocket
            self.sent_payloads.append(payload)

        def disconnect(self, websocket) -> None:
            self.disconnected.append(websocket)

    class DummyWebSocket:
        def __init__(self) -> None:
            self.query_params = {"token": "demo-token"}
            self.closed: list[tuple[int, str]] = []
            self.sent_text: list[str] = []

        async def close(self, code: int, reason: str = "") -> None:
            self.closed.append((code, reason))

        async def receive_text(self) -> str:
            return "ping"

        async def send_text(self, value: str) -> None:
            self.sent_text.append(value)

    async def fake_build_full_state():
        return {"type": "full_state"}

    manager = StubManager()
    websocket = DummyWebSocket()

    monkeypatch.setattr(ws_module, "SessionService", StubSessionService)
    monkeypatch.setattr(ws_module, "ws_manager", manager)
    monkeypatch.setattr(ws_module, "build_full_state", fake_build_full_state)

    asyncio.run(ws_module.websocket_endpoint(websocket))

    assert manager.connected == ["demo-token"]
    assert manager.sent_payloads == [{"type": "full_state"}]
    assert websocket.closed == [(4001, "Session expired")]
    assert websocket.sent_text == []
    assert manager.disconnected == [websocket]


def test_websocket_endpoint_disconnects_cleanly_on_websocket_close(monkeypatch):
    from app.api.routes import ws as ws_module

    class StubSessionService:
        def validate_token(self, token, *, touch=False):
            del token
            del touch
            return True, "admin", None

    class StubManager:
        def __init__(self) -> None:
            self.disconnected: list[object] = []

        async def connect(self, websocket, *, token: str) -> None:
            del websocket
            del token

        async def send_to(self, websocket, payload) -> None:
            del websocket
            del payload

        def disconnect(self, websocket) -> None:
            self.disconnected.append(websocket)

    class DummyWebSocket:
        def __init__(self) -> None:
            self.query_params = {"token": "demo-token"}

        async def receive_text(self) -> str:
            raise WebSocketDisconnect(code=1000)

    manager = StubManager()
    websocket = DummyWebSocket()

    monkeypatch.setattr(ws_module, "SessionService", StubSessionService)
    monkeypatch.setattr(ws_module, "ws_manager", manager)
    monkeypatch.setattr(ws_module, "build_full_state", lambda: {"type": "full_state"})

    asyncio.run(ws_module.websocket_endpoint(websocket))

    assert manager.disconnected == [websocket]


def test_websocket_endpoint_logs_unexpected_errors_and_disconnects(monkeypatch):
    from app.api.routes import ws as ws_module

    class StubSessionService:
        def validate_token(self, token, *, touch=False):
            del token
            del touch
            return True, "admin", None

    class StubManager:
        def __init__(self) -> None:
            self.disconnected: list[object] = []

        async def connect(self, websocket, *, token: str) -> None:
            del websocket
            del token

        async def send_to(self, websocket, payload) -> None:
            del websocket
            del payload

        def disconnect(self, websocket) -> None:
            self.disconnected.append(websocket)

    class DummyWebSocket:
        def __init__(self) -> None:
            self.query_params = {"token": "demo-token"}

        async def receive_text(self) -> str:
            raise RuntimeError("broken socket")

    messages: list[str] = []
    manager = StubManager()
    websocket = DummyWebSocket()

    monkeypatch.setattr(ws_module, "SessionService", StubSessionService)
    monkeypatch.setattr(ws_module, "ws_manager", manager)
    monkeypatch.setattr(ws_module, "build_full_state", lambda: {"type": "full_state"})
    monkeypatch.setattr(ws_module.logger, "exception", lambda message: messages.append(message))

    asyncio.run(ws_module.websocket_endpoint(websocket))

    assert messages == ["Unexpected websocket error"]
    assert manager.disconnected == [websocket]
