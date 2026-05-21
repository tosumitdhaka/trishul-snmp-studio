#!/usr/bin/env python3
"""Release gate for Trishul SNMP Suite 2.0.0.

This gate covers the shipped 2.0 app path:
frontend build, backend bootstrap, schema upgrade, migration validation,
coverage thresholds, and optional live-runtime checks.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = ROOT_DIR / "frontend"
BACKEND_DIR = ROOT_DIR / "backend"
VENV_DIR = ROOT_DIR / ".venv" / "bin"
PROJECT_PYTHON = VENV_DIR / "python"
PROJECT_PYTEST = VENV_DIR / "pytest"


def run_step(label: str, command: list[str], *, cwd: Path, env: dict[str, str]) -> None:
    print(f"[release-gate] {label}", flush=True)
    subprocess.run(command, cwd=cwd, env=env, check=True)


def main() -> int:
    temp_root = Path(tempfile.mkdtemp(prefix="trishul-release-gate-"))
    env = os.environ.copy()
    env["TRISHUL_DATA_DIR"] = str(temp_root / "data")
    live_runtime_enabled = env.get("TRISHUL_ENABLE_LIVE_SNMP_RUNTIME") == "1"
    python_executable = str(PROJECT_PYTHON if PROJECT_PYTHON.exists() else sys.executable)
    pytest_executable = str(PROJECT_PYTEST if PROJECT_PYTEST.exists() else shutil.which("pytest") or "pytest")

    try:
        run_step(
            "frontend build",
            ["npm", "run", "build"],
            cwd=FRONTEND_DIR,
            env=env,
        )

        run_step(
            "backend startup bootstrap smoke",
            [
                python_executable,
                "-c",
                (
                    "import anyio\n"
                    "from app.main import create_app\n"
                    "app = create_app()\n"
                    "async def main():\n"
                    "    async with app.router.lifespan_context(app):\n"
                    "        print('backend lifespan ok')\n"
                    "anyio.run(main)"
                ),
            ],
            cwd=BACKEND_DIR,
            env=env,
        )

        run_step(
            "alembic upgrade head",
            [
                python_executable,
                "-m",
                "alembic",
                "-c",
                str(ROOT_DIR / "alembic.ini"),
                "upgrade",
                "head",
            ],
            cwd=ROOT_DIR,
            env=env,
        )

        run_step(
            "backend coverage + migration gate",
            [
                python_executable,
                str(ROOT_DIR / "scripts" / "check_backend_coverage.py"),
            ],
            cwd=ROOT_DIR,
            env=env,
        )

        if live_runtime_enabled:
            run_step(
                "live runtime tests",
                [
                    pytest_executable,
                    "backend/tests/live",
                    "-q",
                ],
                cwd=ROOT_DIR,
                env=env,
            )
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)

    print("[release-gate] 2.0.0 checks completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
