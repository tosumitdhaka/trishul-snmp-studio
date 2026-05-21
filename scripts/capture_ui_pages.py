#!/usr/bin/env python3
"""Capture authenticated Trishul UI pages via Chrome DevTools Protocol."""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import time
import urllib.request
from pathlib import Path
from typing import Any

import websockets


PAGES: list[tuple[str, str]] = [
    ("dashboard", "Dashboard"),
    ("simulator", "SNMP Simulator"),
    ("walker", "Walk & Parse"),
    ("traps", "Traps"),
    ("browser", "MIB Browser"),
    ("mibs", "MIB Manager"),
    ("settings", "Settings"),
]


def normalize_themes(values: list[str] | None) -> list[str]:
    return values or ["light", "dark"]


def normalize_pages(values: list[str] | None) -> list[tuple[str, str]]:
    if not values:
        return PAGES
    allowed = {key: title for key, title in PAGES}
    selected: list[tuple[str, str]] = []
    for key in values:
        if key not in allowed:
            raise SystemExit(f"Unknown page '{key}'. Choices: {', '.join(allowed)}")
        selected.append((key, allowed[key]))
    return selected


def fetch_json(url: str) -> Any:
    with urllib.request.urlopen(url, timeout=5) as response:
        return json.loads(response.read().decode())


async def wait_for_expression(
    send: Any,
    expression: str,
    *,
    timeout: float = 15.0,
    interval: float = 0.2,
) -> Any:
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = await send(
            "Runtime.evaluate",
            {
                "expression": expression,
                "returnByValue": True,
            },
        )
        value = result.get("result", {}).get("value")
        if value:
            return value
        await asyncio.sleep(interval)
    raise TimeoutError(expression)


async def capture_pages(
    *,
    base_url: str,
    token: str,
    outdir: Path,
    debugger_url: str,
    width: int,
    height: int,
    themes: list[str],
    pages: list[tuple[str, str]],
    settle_ms: int,
) -> list[Path]:
    targets = fetch_json(f"{debugger_url.rstrip('/')}/json/list")
    page = next(item for item in targets if item.get("type") == "page")
    ws_url = page["webSocketDebuggerUrl"]
    outdir.mkdir(parents=True, exist_ok=True)

    async with websockets.connect(ws_url, max_size=50_000_000) as ws:
        next_id = 0
        pending: dict[int, asyncio.Future[dict[str, Any]]] = {}

        async def receiver() -> None:
            while True:
                message = json.loads(await ws.recv())
                msg_id = message.get("id")
                if msg_id in pending:
                    pending.pop(msg_id).set_result(message)

        receiver_task = asyncio.create_task(receiver())

        async def send(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
            nonlocal next_id
            next_id += 1
            msg_id = next_id
            future: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
            pending[msg_id] = future
            await ws.send(json.dumps({"id": msg_id, "method": method, "params": params or {}}))
            response = await future
            if "error" in response:
                raise RuntimeError(f"{method}: {response['error']}")
            return response.get("result", {})

        try:
            await send("Page.enable")
            await send("Runtime.enable")
            await send(
                "Emulation.setDeviceMetricsOverride",
                {
                    "width": width,
                    "height": height,
                    "deviceScaleFactor": 1,
                    "mobile": False,
                },
            )

            await send("Page.navigate", {"url": base_url})
            await wait_for_expression(send, 'document.readyState === "complete"', timeout=15)
            await asyncio.sleep(1.0)

            bootstrap_expr = """
                sessionStorage.setItem("snmp_token", __TOKEN__);
                hideAuthLoading();
                updateUserUI("admin");
                showApp();
                window.location.hash = "#dashboard";
                true;
            """.replace("__TOKEN__", json.dumps(token))
            await send(
                "Runtime.evaluate",
                {
                    "expression": bootstrap_expr,
                    "returnByValue": True,
                },
            )

            await wait_for_expression(
                send,
                '!!document.getElementById("wrapper")'
                ' && !document.getElementById("wrapper").classList.contains("d-none")',
            )
            await wait_for_expression(
                send,
                'document.getElementById("page-title")'
                ' && document.getElementById("page-title").textContent.trim() === "Dashboard"',
            )
            await asyncio.sleep(1.5)

            captured: list[Path] = []
            settle_delay = max(settle_ms, 0) / 1000

            for theme in themes:
                await send(
                    "Runtime.evaluate",
                    {
                        "expression": f'TrishulUtils.applyTheme("{theme}"); true;',
                        "returnByValue": True,
                    },
                )
                await asyncio.sleep(0.5)

                for page_key, page_title in pages:
                    await send(
                        "Runtime.evaluate",
                        {
                            "expression": f'window.location.hash = "#{page_key}"; true;',
                            "returnByValue": True,
                        },
                    )
                    await wait_for_expression(
                        send,
                        f'document.getElementById("page-title")'
                        f' && document.getElementById("page-title").textContent.trim() === {json.dumps(page_title)}',
                    )
                    await wait_for_expression(
                        send,
                        'document.querySelector("#main-content")'
                        ' && document.querySelector("#main-content").children.length > 0',
                    )
                    await asyncio.sleep(settle_delay)
                    screenshot = await send(
                        "Page.captureScreenshot",
                        {"format": "png", "fromSurface": True},
                    )
                    path = outdir / f"{page_key}-{theme}.png"
                    path.write_bytes(base64.b64decode(screenshot["data"]))
                    captured.append(path)

            return captured
        finally:
            receiver_task.cancel()
            try:
                await receiver_task
            except BaseException:
                pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8980")
    parser.add_argument("--token", required=True)
    parser.add_argument("--debugger-url", default="http://127.0.0.1:9222")
    parser.add_argument("--outdir", default="/tmp/trishul-ui-pages")
    parser.add_argument("--width", type=int, default=1440)
    parser.add_argument("--height", type=int, default=1100)
    parser.add_argument(
        "--page",
        action="append",
        dest="pages",
        choices=[key for key, _title in PAGES],
        help="Page(s) to capture. Defaults to all major routes.",
    )
    parser.add_argument(
        "--settle-ms",
        type=int,
        default=2200,
        help="Extra wait time after each route renders before capturing.",
    )
    parser.add_argument(
        "--theme",
        action="append",
        dest="themes",
        choices=("light", "dark"),
        help="Theme(s) to capture. Defaults to both light and dark.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    themes = normalize_themes(args.themes)
    pages = normalize_pages(args.pages)
    captured = asyncio.run(
        capture_pages(
            base_url=args.base_url,
            token=args.token,
            debugger_url=args.debugger_url,
            outdir=Path(args.outdir),
            width=args.width,
            height=args.height,
            themes=themes,
            pages=pages,
            settle_ms=args.settle_ms,
        )
    )
    for path in captured:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
