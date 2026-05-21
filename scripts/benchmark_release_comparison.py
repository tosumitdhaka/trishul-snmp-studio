#!/usr/bin/env python3
"""Benchmark Trishul SNMP Suite old-line vs 2.0.0 release behavior."""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import socket
import statistics
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import requests

try:
    import websockets
except ImportError as exc:  # pragma: no cover - runtime safeguard
    raise SystemExit("The 'websockets' package is required to run this benchmark.") from exc


DEFAULT_OLD_REPO = Path("/home/dhaka/trishul3/trishul-snmp-suite-old/trishul-snmp-suite")
DEFAULT_CURRENT_REPO = Path("/home/dhaka/trishul3/trishul-snmp-suite")
DEFAULT_JUNIPER_DIR = Path("/home/dhaka/test/mibs/juniper")
DEFAULT_OUTPUT_DIR = DEFAULT_CURRENT_REPO / "docs" / "archive" / "research"
DEFAULT_OLD_IMAGE = "ghcr.io/tosumitdhaka/trishul-snmp-suite:1.4.1"
DEFAULT_NEW_IMAGE = "trishul-snmp-suite-local:2.0.0"

TRAP_PAYLOAD = {
    "target": "127.0.0.1",
    "port": 1162,
    "community": "public",
    "oid": "1.3.6.1.6.3.1.1.5.3",
    "varbinds": [
        {
            "oid": "1.3.6.1.2.1.1.5.0",
            "type": "String",
            "value": "bench-agent",
        }
    ],
}

WALK_PAYLOAD = {
    "target": "127.0.0.1",
    "port": 1061,
    "community": "public",
    "oid": "1.3.6.1.2.1.2.2",
    "parse": True,
    "use_mibs": True,
}

LOGIN_PAYLOAD = {"username": "admin", "password": "admin123"}
SETTINGS_AUTO_FETCH_PAYLOAD = {
    "auto_start_simulator": False,
    "auto_start_trap_receiver": False,
    "session_timeout": 3600,
    "mib_auto_fetch": True,
}


@dataclass(frozen=True)
class ReleaseSpec:
    key: str
    label: str
    image: str
    http_port: int
    container_name: str
    volume_name: str

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.http_port}"


def run(
    args: list[str],
    *,
    check: bool = True,
    capture_output: bool = True,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        check=check,
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=capture_output,
    )


def sanitize_slug(value: str) -> str:
    cleaned = []
    for char in value.lower():
        if char.isalnum():
            cleaned.append(char)
        elif char in {"-", "_"}:
            cleaned.append("-")
    slug = "".join(cleaned).strip("-")
    return slug or "bench"


def docker_exists(name: str, *, object_type: str = "container") -> bool:
    inspect_args = ["docker", "inspect", name]
    if object_type == "image":
        inspect_args = ["docker", "image", "inspect", name]
    if object_type == "volume":
        inspect_args = ["docker", "volume", "inspect", name]
    completed = run(inspect_args, check=False)
    return completed.returncode == 0


def docker_remove_container(name: str) -> None:
    if docker_exists(name):
        run(["docker", "rm", "-f", name], check=False)


def docker_remove_volume(name: str) -> None:
    if docker_exists(name, object_type="volume"):
        run(["docker", "volume", "rm", "-f", name], check=False)


def docker_logs(name: str, tail: int = 200) -> str:
    completed = run(["docker", "logs", "--tail", str(tail), name], check=False)
    if completed.returncode != 0:
        return completed.stdout + completed.stderr
    return (completed.stdout or "") + (completed.stderr or "")


def docker_image_size_bytes(image: str) -> int | None:
    completed = run(
        ["docker", "image", "inspect", image, "--format", "{{.Size}}"],
        check=False,
    )
    if completed.returncode != 0:
        return None
    try:
        return int((completed.stdout or "").strip())
    except ValueError:
        return None


def wait_for_http(url: str, *, timeout_s: float = 180.0, interval_s: float = 0.5) -> tuple[float, dict[str, Any]]:
    started = time.perf_counter()
    last_error: str | None = None
    while (time.perf_counter() - started) < timeout_s:
        try:
            response = requests.get(url, timeout=5)
            if response.ok:
                return time.perf_counter() - started, response.json()
            last_error = f"HTTP {response.status_code}: {response.text[:200]}"
        except Exception as exc:  # pragma: no cover - network wait loop
            last_error = str(exc)
        time.sleep(interval_s)
    raise RuntimeError(f"Timed out waiting for {url}: {last_error}")


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    ordered = sorted(values)
    if pct <= 0:
        return ordered[0]
    if pct >= 100:
        return ordered[-1]
    rank = (len(ordered) - 1) * (pct / 100)
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return ordered[lower]
    weight = rank - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def summarize_timings(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {
            "count": 0,
            "min_ms": None,
            "median_ms": None,
            "mean_ms": None,
            "p95_ms": None,
            "max_ms": None,
        }
    return {
        "count": len(values),
        "min_ms": min(values),
        "median_ms": statistics.median(values),
        "mean_ms": statistics.fmean(values),
        "p95_ms": percentile(values, 95),
        "max_ms": max(values),
    }


def time_request(
    session: requests.Session,
    method: str,
    url: str,
    *,
    repeat: int = 1,
    timeout: float = 30.0,
    expected_status: int = 200,
    **kwargs: Any,
) -> tuple[list[float], list[dict[str, Any]]]:
    timings: list[float] = []
    payloads: list[dict[str, Any]] = []
    for _ in range(repeat):
        started = time.perf_counter()
        response = session.request(method, url, timeout=timeout, **kwargs)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        if response.status_code != expected_status:
            raise RuntimeError(
                f"{method} {url} returned {response.status_code}: {response.text[:400]}"
            )
        timings.append(elapsed_ms)
        try:
            payloads.append(response.json())
        except ValueError:
            payloads.append({"raw_text": response.text})
    return timings, payloads


def count_trap_events(payload: dict[str, Any]) -> int:
    if isinstance(payload.get("data"), list):
        return len(payload["data"])
    if isinstance(payload.get("traps"), list):
        return len(payload["traps"])
    return 0


def file_line_count(path: Path) -> int:
    try:
        return len(path.read_text(errors="ignore").splitlines())
    except OSError:
        return 0


def collect_code_metrics(root: Path, *, current: bool) -> dict[str, Any]:
    backend_root = root / "backend"
    frontend_root = root / "frontend"
    test_files = sorted((backend_root / "tests").glob("test_*.py"))
    if current:
        backend_source_files = sorted(
            p
            for p in backend_root.rglob("*.py")
            if "tests" not in p.parts and "data" not in p.parts and "__pycache__" not in p.parts
        )
        frontend_source_files = sorted(
            p
            for p in frontend_root.rglob("*")
            if p.is_file()
            and "dist" not in p.parts
            and p.suffix.lower() in {".html", ".js", ".css", ".mjs"}
        )
        migrations = sorted((backend_root / "alembic" / "versions").glob("*.py"))
        models = sorted((backend_root / "app" / "models").glob("*.py"))
        routes = sorted((backend_root / "app" / "api" / "routes").glob("*.py"))
    else:
        backend_source_files = sorted(
            p
            for p in backend_root.rglob("*.py")
            if "tests" not in p.parts and "__pycache__" not in p.parts
        )
        frontend_source_files = sorted(
            p
            for p in (frontend_root / "src").rglob("*")
            if p.is_file() and p.suffix.lower() in {".html", ".js", ".css"}
        )
        migrations = []
        models = []
        routes = sorted((backend_root / "api" / "routers").glob("*.py"))

    requirements = [
        line.strip()
        for line in (backend_root / "requirements.txt").read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]

    return {
        "repo_path": str(root),
        "backend_source_files": len(backend_source_files),
        "backend_source_lines": sum(file_line_count(path) for path in backend_source_files),
        "frontend_source_files": len(frontend_source_files),
        "frontend_source_lines": sum(file_line_count(path) for path in frontend_source_files),
        "test_files": len(test_files),
        "test_lines": sum(file_line_count(path) for path in test_files),
        "test_functions": sum(path.read_text(errors="ignore").count("def test_") for path in test_files),
        "route_files": len(routes),
        "model_files": len(models),
        "migration_files": len(migrations),
        "dependency_count": len(requirements),
        "dependencies": requirements,
    }


def detect_git_baseline(root: Path) -> dict[str, Any]:
    describe = run(["git", "describe", "--tags", "--always"], cwd=root, check=False)
    tags = run(["git", "tag", "--list"], cwd=root, check=False)
    branches = run(["git", "branch", "-a"], cwd=root, check=False)
    return {
        "describe": (describe.stdout or "").strip(),
        "tags": [line.strip() for line in (tags.stdout or "").splitlines() if line.strip()],
        "branches": [line.strip() for line in (branches.stdout or "").splitlines() if line.strip()],
    }


def juniper_source_files(directory: Path) -> list[Path]:
    return sorted(
        path
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in {".txt", ".mib", ".my"}
    )


async def measure_ws_handshake(base_url: str, token: str) -> dict[str, Any]:
    ws_url = base_url.replace("http://", "ws://").replace("https://", "wss://") + f"/api/ws?token={token}"
    started = time.perf_counter()
    async with websockets.connect(ws_url, open_timeout=10, max_size=10_000_000) as websocket:
        raw = await asyncio.wait_for(websocket.recv(), timeout=10)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        message = json.loads(raw)
        return {
            "handshake_ms": elapsed_ms,
            "first_message_type": message.get("type"),
        }


async def measure_ws_trap_delivery(
    *,
    base_url: str,
    token: str,
    send_trap: Callable[[], dict[str, Any]],
    timeout_s: float = 15.0,
) -> dict[str, Any]:
    ws_url = base_url.replace("http://", "ws://").replace("https://", "wss://") + f"/api/ws?token={token}"
    async with websockets.connect(ws_url, open_timeout=10, max_size=10_000_000) as websocket:
        first = json.loads(await asyncio.wait_for(websocket.recv(), timeout=10))
        started = time.perf_counter()
        send_result = await asyncio.to_thread(send_trap)
        while (time.perf_counter() - started) < timeout_s:
            remaining = max(0.1, timeout_s - (time.perf_counter() - started))
            raw = await asyncio.wait_for(websocket.recv(), timeout=remaining)
            if raw == "pong":
                continue
            message = json.loads(raw)
            if message.get("type") == "trap":
                return {
                    "ws_connected_type": first.get("type"),
                    "send_ms": send_result["send_ms"],
                    "delivery_ms": (time.perf_counter() - started) * 1000.0,
                    "trap_message_type": message.get("type"),
                    "send_response": send_result["response"],
                }
        raise RuntimeError("Timed out waiting for trap message over websocket.")


def benchmark_release(spec: ReleaseSpec, juniper_files: list[Path]) -> dict[str, Any]:
    session = requests.Session()
    container_started = False
    result: dict[str, Any] = {
        "spec": asdict(spec),
        "image_size_bytes": docker_image_size_bytes(spec.image),
        "container_logs_tail": None,
    }

    def send_trap() -> dict[str, Any]:
        send_timings, payloads = time_request(
            session,
            "POST",
            f"{spec.base_url}/api/traps/send",
            json=TRAP_PAYLOAD,
            repeat=1,
            timeout=30.0,
        )
        return {"send_ms": send_timings[0], "response": payloads[0]}

    try:
        docker_remove_container(spec.container_name)
        docker_remove_volume(spec.volume_name)
        run(["docker", "volume", "create", spec.volume_name])
        run(
            [
                "docker",
                "run",
                "-d",
                "--name",
                spec.container_name,
                "-v",
                f"{spec.volume_name}:/app/backend/data",
                "-p",
                f"{spec.http_port}:8000",
                spec.image,
            ]
        )
        container_started = True

        if result["image_size_bytes"] is None:
            result["image_size_bytes"] = docker_image_size_bytes(spec.image)

        startup_seconds, meta = wait_for_http(f"{spec.base_url}/api/meta")
        result["startup"] = {
            "ready_seconds": startup_seconds,
            "meta": meta,
        }

        login_timings, login_payloads = time_request(
            session,
            "POST",
            f"{spec.base_url}/api/settings/login",
            json=LOGIN_PAYLOAD,
            repeat=5,
            timeout=15.0,
        )
        token = str(login_payloads[-1]["token"])
        session.headers.update({"X-Auth-Token": token})
        result["login"] = {
            **summarize_timings(login_timings),
            "username": login_payloads[-1].get("username"),
        }

        result["websocket"] = asyncio.run(measure_ws_handshake(spec.base_url, token))

        stats_timings, stats_payloads = time_request(
            session,
            "GET",
            f"{spec.base_url}/api/stats/",
            repeat=10,
            timeout=15.0,
        )
        result["stats"] = {
            **summarize_timings(stats_timings),
            "sample": stats_payloads[-1],
        }

        mibs_status_timings, mibs_status_payloads = time_request(
            session,
            "GET",
            f"{spec.base_url}/api/mibs/status",
            repeat=5,
            timeout=15.0,
        )
        result["mibs_before"] = {
            **summarize_timings(mibs_status_timings),
            "status": mibs_status_payloads[-1],
        }

        sim_start_timings, sim_start_payloads = time_request(
            session,
            "POST",
            f"{spec.base_url}/api/simulator/start",
            json={"port": 1061, "community": "public"},
            repeat=1,
            timeout=30.0,
        )
        result["simulator_start"] = {
            "timing_ms": sim_start_timings[0],
            "response": sim_start_payloads[0],
        }

        walk_timings, walk_payloads = time_request(
            session,
            "POST",
            f"{spec.base_url}/api/walk/execute",
            json=WALK_PAYLOAD,
            repeat=5,
            timeout=60.0,
        )
        last_walk = walk_payloads[-1]
        result["walk"] = {
            **summarize_timings(walk_timings),
            "mode": last_walk.get("mode"),
            "count": last_walk.get("count"),
        }

        trap_start_timings, trap_start_payloads = time_request(
            session,
            "POST",
            f"{spec.base_url}/api/traps/start",
            json={"port": 1162, "community": "public", "resolve_mibs": True},
            repeat=1,
            timeout=30.0,
        )
        result["trap_listener_start"] = {
            "timing_ms": trap_start_timings[0],
            "response": trap_start_payloads[0],
        }

        time_request(
            session,
            "DELETE",
            f"{spec.base_url}/api/traps/",
            repeat=1,
            timeout=15.0,
        )
        before_traps = session.get(f"{spec.base_url}/api/traps/", timeout=15.0)
        before_traps.raise_for_status()
        before_count = count_trap_events(before_traps.json())

        trap_flow = asyncio.run(
            measure_ws_trap_delivery(
                base_url=spec.base_url,
                token=token,
                send_trap=send_trap,
            )
        )
        after_deadline = time.perf_counter() + 15.0
        poll_visibility_ms: float | None = None
        while time.perf_counter() < after_deadline:
            response = session.get(f"{spec.base_url}/api/traps/", timeout=15.0)
            response.raise_for_status()
            current_count = count_trap_events(response.json())
            if current_count > before_count:
                poll_visibility_ms = (15.0 - (after_deadline - time.perf_counter())) * 1000.0
                break
            time.sleep(0.1)
        result["trap"] = {
            **trap_flow,
            "poll_visibility_ms": poll_visibility_ms,
            "before_count": before_count,
            "after_count": current_count if "current_count" in locals() else before_count,
        }

        settings_timings, settings_payloads = time_request(
            session,
            "POST",
            f"{spec.base_url}/api/settings/app",
            json=SETTINGS_AUTO_FETCH_PAYLOAD,
            repeat=1,
            timeout=30.0,
        )
        result["settings_update"] = {
            "timing_ms": settings_timings[0],
            "response": settings_payloads[0],
        }

        multipart_files = [
            ("files", (path.name, path.read_bytes(), "text/plain"))
            for path in juniper_files
        ]
        upload_timings, upload_payloads = time_request(
            session,
            "POST",
            f"{spec.base_url}/api/mibs/upload",
            files=multipart_files,
            repeat=1,
            timeout=1800.0,
        )
        upload_payload = upload_payloads[0]
        result["mib_upload"] = {
            "timing_ms": upload_timings[0],
            "response": upload_payload,
            "loaded_results": sum(
                1 for entry in upload_payload.get("results", []) if entry.get("status") == "loaded"
            ),
            "failed_results": sum(
                1 for entry in upload_payload.get("results", []) if entry.get("status") == "failed"
            ),
        }

        after_status = session.get(f"{spec.base_url}/api/mibs/status", timeout=30.0)
        after_status.raise_for_status()
        result["mibs_after"] = after_status.json()

        return result
    except Exception as exc:
        result["error"] = str(exc)
        if container_started:
            result["container_logs_tail"] = docker_logs(spec.container_name)
        return result
    finally:
        if container_started:
            if result.get("container_logs_tail") is None:
                result["container_logs_tail"] = docker_logs(spec.container_name, tail=120)
            docker_remove_container(spec.container_name)
        docker_remove_volume(spec.volume_name)


def format_ms(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.1f}"


def format_seconds(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.2f}"


def format_bytes_to_mb(value: int | None) -> str:
    if value is None:
        return "-"
    return f"{value / (1024 * 1024):.1f}"


def build_report_markdown(report: dict[str, Any]) -> str:
    generated_at = report["generated_at"]
    old_key = "old_line"
    new_key = "v2_0_0"
    old_live = report["live"].get(old_key, {})
    new_live = report["live"].get(new_key, {})
    old_code = report["code_metrics"].get(old_key, {})
    new_code = report["code_metrics"].get(new_key, {})
    corpus = report["juniper_corpus"]

    lines = [
        "# Trishul SNMP Suite Release Comparison",
        "",
        f"Generated: `{generated_at}`",
        "",
        "## Baseline Note",
        "",
        "The local pre-2.0 checkout available in this workspace identifies as the `1.4.1` line.",
        "No local `1.5.1` tag or branch was available, so the old-line comparison below uses that",
        "released pre-2.0 baseline rather than claiming an unavailable `1.5.1` artifact.",
        "",
        "## Corpus",
        "",
        f"- Juniper source directory: `{corpus['directory']}`",
        f"- Compile source files: `{corpus['file_count']}`",
        f"- Total source bytes: `{corpus['total_bytes']}`",
        "",
        "## Static Code Metrics",
        "",
        "| Metric | Old line | 2.0.0 |",
        "| --- | ---: | ---: |",
        f"| Backend source files | {old_code.get('backend_source_files', '-')} | {new_code.get('backend_source_files', '-')} |",
        f"| Backend source lines | {old_code.get('backend_source_lines', '-')} | {new_code.get('backend_source_lines', '-')} |",
        f"| Frontend source files | {old_code.get('frontend_source_files', '-')} | {new_code.get('frontend_source_files', '-')} |",
        f"| Frontend source lines | {old_code.get('frontend_source_lines', '-')} | {new_code.get('frontend_source_lines', '-')} |",
        f"| Test files | {old_code.get('test_files', '-')} | {new_code.get('test_files', '-')} |",
        f"| Test lines | {old_code.get('test_lines', '-')} | {new_code.get('test_lines', '-')} |",
        f"| Test functions | {old_code.get('test_functions', '-')} | {new_code.get('test_functions', '-')} |",
        f"| Route files | {old_code.get('route_files', '-')} | {new_code.get('route_files', '-')} |",
        f"| Model files | {old_code.get('model_files', '-')} | {new_code.get('model_files', '-')} |",
        f"| Migration files | {old_code.get('migration_files', '-')} | {new_code.get('migration_files', '-')} |",
        f"| Backend dependency count | {old_code.get('dependency_count', '-')} | {new_code.get('dependency_count', '-')} |",
        "",
        "## Live Runtime Metrics",
        "",
        "| Metric | Old line | 2.0.0 |",
        "| --- | ---: | ---: |",
        f"| Image size (MB) | {format_bytes_to_mb(old_live.get('image_size_bytes'))} | {format_bytes_to_mb(new_live.get('image_size_bytes'))} |",
        f"| Ready time (s) | {format_seconds((old_live.get('startup') or {}).get('ready_seconds'))} | {format_seconds((new_live.get('startup') or {}).get('ready_seconds'))} |",
        f"| Login median (ms) | {format_ms((old_live.get('login') or {}).get('median_ms'))} | {format_ms((new_live.get('login') or {}).get('median_ms'))} |",
        f"| `/api/stats/` median (ms) | {format_ms((old_live.get('stats') or {}).get('median_ms'))} | {format_ms((new_live.get('stats') or {}).get('median_ms'))} |",
        f"| `/api/mibs/status` median (ms) | {format_ms((old_live.get('mibs_before') or {}).get('median_ms'))} | {format_ms((new_live.get('mibs_before') or {}).get('median_ms'))} |",
        f"| WebSocket handshake (ms) | {format_ms((old_live.get('websocket') or {}).get('handshake_ms'))} | {format_ms((new_live.get('websocket') or {}).get('handshake_ms'))} |",
        f"| Simulator start (ms) | {format_ms((old_live.get('simulator_start') or {}).get('timing_ms'))} | {format_ms((new_live.get('simulator_start') or {}).get('timing_ms'))} |",
        f"| Walk median (ms) | {format_ms((old_live.get('walk') or {}).get('median_ms'))} | {format_ms((new_live.get('walk') or {}).get('median_ms'))} |",
        f"| Walk count | {(old_live.get('walk') or {}).get('count', '-')} | {(new_live.get('walk') or {}).get('count', '-')} |",
        f"| Trap listener start (ms) | {format_ms((old_live.get('trap_listener_start') or {}).get('timing_ms'))} | {format_ms((new_live.get('trap_listener_start') or {}).get('timing_ms'))} |",
        f"| Trap send call (ms) | {format_ms((old_live.get('trap') or {}).get('send_ms'))} | {format_ms((new_live.get('trap') or {}).get('send_ms'))} |",
        f"| Trap delivery over WS (ms) | {format_ms((old_live.get('trap') or {}).get('delivery_ms'))} | {format_ms((new_live.get('trap') or {}).get('delivery_ms'))} |",
        "",
        "## 168-File Juniper Upload + Compile",
        "",
        "This is a single cold run per release on a clean throwaway data volume with auto-fetch enabled.",
        "That keeps the comparison meaningful while avoiding cached dependencies from earlier attempts.",
        "",
        "| Metric | Old line | 2.0.0 |",
        "| --- | ---: | ---: |",
        f"| Upload + compile time (ms) | {format_ms((old_live.get('mib_upload') or {}).get('timing_ms'))} | {format_ms((new_live.get('mib_upload') or {}).get('timing_ms'))} |",
        f"| Upload loaded rows | {(old_live.get('mib_upload') or {}).get('loaded_results', '-')} | {(new_live.get('mib_upload') or {}).get('loaded_results', '-')} |",
        f"| Upload failed rows | {(old_live.get('mib_upload') or {}).get('failed_results', '-')} | {(new_live.get('mib_upload') or {}).get('failed_results', '-')} |",
        f"| MIB status loaded after upload | {(old_live.get('mibs_after') or {}).get('loaded', '-')} | {(new_live.get('mibs_after') or {}).get('loaded', '-')} |",
        f"| MIB status failed after upload | {(old_live.get('mibs_after') or {}).get('failed', '-')} | {(new_live.get('mibs_after') or {}).get('failed', '-')} |",
        "",
        "## Notes",
        "",
        "- The old-line code baseline is `1.4.1` because no local `1.5.1` artifact was present.",
        "- The Juniper compile benchmark uses the same 168 source files for both runs.",
        "- Upload timing includes save, dependency fetch, compile, and activation/reload behavior because that is what operators actually experience.",
        "- Raw benchmark JSON is stored next to this report for auditability.",
        "",
    ]
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--current-repo", type=Path, default=DEFAULT_CURRENT_REPO)
    parser.add_argument("--old-repo", type=Path, default=DEFAULT_OLD_REPO)
    parser.add_argument("--juniper-dir", type=Path, default=DEFAULT_JUNIPER_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--old-image", default=DEFAULT_OLD_IMAGE)
    parser.add_argument("--new-image", default=DEFAULT_NEW_IMAGE)
    parser.add_argument("--old-port", type=int, default=19081)
    parser.add_argument("--new-port", type=int, default=29080)
    parser.add_argument("--label", default=datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    label = sanitize_slug(args.label)
    current_repo = args.current_repo.resolve()
    old_repo = args.old_repo.resolve()
    juniper_dir = args.juniper_dir.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if not current_repo.exists():
        raise SystemExit(f"Current repo not found: {current_repo}")
    if not old_repo.exists():
        raise SystemExit(f"Old repo not found: {old_repo}")
    if not juniper_dir.exists():
        raise SystemExit(f"Juniper source directory not found: {juniper_dir}")

    juniper_files = juniper_source_files(juniper_dir)
    if not juniper_files:
        raise SystemExit(f"No Juniper source files found in {juniper_dir}")

    report: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "host": {
            "hostname": socket.gethostname(),
            "python": sys.version,
            "cwd": os.getcwd(),
        },
        "baseline": {
            "old_line": detect_git_baseline(old_repo),
            "v2_0_0": detect_git_baseline(current_repo),
        },
        "juniper_corpus": {
            "directory": str(juniper_dir),
            "file_count": len(juniper_files),
            "total_bytes": sum(path.stat().st_size for path in juniper_files),
            "sample": [path.name for path in juniper_files[:10]],
        },
        "code_metrics": {
            "old_line": collect_code_metrics(old_repo, current=False),
            "v2_0_0": collect_code_metrics(current_repo, current=True),
        },
        "live": {},
    }

    releases = [
        ReleaseSpec(
            key="old_line",
            label="Old line (1.4.1 baseline)",
            image=args.old_image,
            http_port=args.old_port,
            container_name=f"trishul-bench-old-{label}",
            volume_name=f"trishul-bench-old-data-{label}",
        ),
        ReleaseSpec(
            key="v2_0_0",
            label="2.0.0",
            image=args.new_image,
            http_port=args.new_port,
            container_name=f"trishul-bench-v2-{label}",
            volume_name=f"trishul-bench-v2-data-{label}",
        ),
    ]

    for spec in releases:
        report["live"][spec.key] = benchmark_release(spec, juniper_files)

    json_path = output_dir / f"release-comparison-{label}.json"
    md_path = output_dir / f"release-comparison-{label}.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    md_path.write_text(build_report_markdown(report))

    print(json_path)
    print(md_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
