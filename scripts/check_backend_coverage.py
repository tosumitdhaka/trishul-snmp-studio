#!/usr/bin/env python3
"""Run the backend test suite with coverage and enforce release thresholds."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_APP_DIR = ROOT_DIR / "backend" / "app"
DEFAULT_TEST_TARGETS = [
    "backend/tests/unit",
    "backend/tests/contract",
    "backend/tests/integration",
]


@dataclass(frozen=True)
class CoverageScope:
    label: str
    paths: tuple[Path, ...]
    minimum: float


@dataclass(frozen=True)
class CoverageMetric:
    label: str
    covered: int
    executable: int
    minimum: float | None = None


@dataclass(frozen=True)
class CoverageDetail:
    path: Path
    covered: int
    executable: int


@dataclass(frozen=True)
class CoverageEvaluation:
    total: CoverageMetric
    scopes: tuple[CoverageMetric, ...]
    lowest_files: tuple[CoverageDetail, ...]
    failures: tuple[str, ...]


CRITICAL_SCOPES = (
    CoverageScope(
        label="api",
        paths=(BACKEND_APP_DIR / "api",),
        minimum=73.0,
    ),
    CoverageScope(
        label="bundle-pipeline",
        paths=(
            BACKEND_APP_DIR / "services" / "bundles.py",
            BACKEND_APP_DIR / "services" / "mib_sources.py",
            BACKEND_APP_DIR / "services" / "mib_mutations.py",
            BACKEND_APP_DIR / "services" / "mibs_service.py",
        ),
        minimum=80.0,
    ),
    CoverageScope(
        label="runtime",
        paths=(BACKEND_APP_DIR / "services" / "runtime.py",),
        minimum=88.0,
    ),
    CoverageScope(
        label="persistence",
        paths=(
            BACKEND_APP_DIR / "db",
            BACKEND_APP_DIR / "models",
            BACKEND_APP_DIR / "services" / "app_settings.py",
            BACKEND_APP_DIR / "services" / "history.py",
            BACKEND_APP_DIR / "services" / "session.py",
            BACKEND_APP_DIR / "services" / "state_store.py",
        ),
        minimum=85.0,
    ),
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Enforce backend release coverage thresholds using pytest-cov.",
    )
    parser.add_argument(
        "--min-total",
        type=float,
        default=80.0,
        help="Minimum total coverage percentage for backend/app.",
    )
    parser.add_argument(
        "--report-limit",
        type=int,
        default=8,
        help="Number of lowest-covered files to print.",
    )
    parser.add_argument(
        "tests",
        nargs="*",
        default=DEFAULT_TEST_TARGETS,
        help="Pytest targets to execute with coverage enabled.",
    )
    parser.add_argument(
        "--report-json",
        default=None,
        help=argparse.SUPPRESS,
    )
    return parser.parse_args()


def _collect_python_files(paths: tuple[Path, ...]) -> list[Path]:
    files: dict[Path, None] = {}
    for path in paths:
        resolved = path.resolve()
        if resolved.is_dir():
            for file_path in resolved.rglob("*.py"):
                if "__pycache__" in file_path.parts or file_path.name == "__init__.py":
                    continue
                files[file_path.resolve()] = None
            continue
        if resolved.is_file() and resolved.name != "__init__.py":
            files[resolved] = None
    return sorted(files)


def _normalize_report_path(filename: str) -> Path:
    path = Path(filename)
    if not path.is_absolute():
        path = ROOT_DIR / path
    return path.resolve()


def _coverage_summary(
    report_files: dict[Path, dict[str, object]],
    files: list[Path],
) -> tuple[int, int, list[tuple[Path, int, int]]]:
    covered = 0
    executable = 0
    details: list[tuple[Path, int, int]] = []
    for file_path in files:
        summary = (report_files.get(file_path) or {}).get("summary") or {}
        file_covered = int(summary.get("covered_lines") or 0)
        file_statements = int(summary.get("num_statements") or 0)
        covered += file_covered
        executable += file_statements
        details.append((file_path, file_covered, file_statements))
    return covered, executable, details


def _format_percent(covered: int, executable: int) -> float:
    if executable == 0:
        return 100.0
    return (covered / executable) * 100.0


def _format_metric(metric: CoverageMetric) -> str:
    threshold_text = "" if metric.minimum is None else f" (min {metric.minimum:.1f}%)"
    return (
        f"[coverage] {metric.label}: {_format_percent(metric.covered, metric.executable):.1f}% "
        f"({metric.covered}/{metric.executable} executable lines){threshold_text}"
    )


def _evaluate_report(
    report: dict[str, object],
    *,
    min_total: float,
    report_limit: int,
) -> CoverageEvaluation:
    report_files = {
        _normalize_report_path(filename): payload
        for filename, payload in report.get("files", {}).items()
    }

    all_files = _collect_python_files((BACKEND_APP_DIR,))
    total_covered, total_executable, file_details = _coverage_summary(report_files, all_files)
    total_metric = CoverageMetric(
        label="backend/app total",
        covered=total_covered,
        executable=total_executable,
        minimum=min_total,
    )

    failures: list[str] = []
    if _format_percent(total_covered, total_executable) < min_total:
        failures.append(
            f"backend/app total coverage "
            f"{_format_percent(total_covered, total_executable):.1f}% is below {min_total:.1f}%."
        )

    scope_metrics: list[CoverageMetric] = []
    for scope in CRITICAL_SCOPES:
        scope_files = _collect_python_files(scope.paths)
        covered, executable, _details = _coverage_summary(report_files, scope_files)
        metric = CoverageMetric(
            label=scope.label,
            covered=covered,
            executable=executable,
            minimum=scope.minimum,
        )
        scope_metrics.append(metric)
        if _format_percent(covered, executable) < scope.minimum:
            failures.append(
                f"{scope.label} coverage {_format_percent(covered, executable):.1f}% "
                f"is below {scope.minimum:.1f}%."
            )

    lowest_files = tuple(
        CoverageDetail(path=file_path, covered=covered, executable=executable)
        for file_path, covered, executable in sorted(
            file_details,
            key=lambda item: (_format_percent(item[1], item[2]), item[0].as_posix()),
        )[: max(0, report_limit)]
    )
    return CoverageEvaluation(
        total=total_metric,
        scopes=tuple(scope_metrics),
        lowest_files=lowest_files,
        failures=tuple(failures),
    )


def _format_evaluation_lines(evaluation: CoverageEvaluation) -> list[str]:
    lines = [_format_metric(evaluation.total)]
    lines.extend(_format_metric(metric) for metric in evaluation.scopes)
    if evaluation.lowest_files:
        lines.append("[coverage] lowest covered files:")
        for detail in evaluation.lowest_files:
            relative_path = detail.path.relative_to(ROOT_DIR)
            lines.append(
                f"  - {relative_path}: {_format_percent(detail.covered, detail.executable):.1f}% "
                f"({detail.covered}/{detail.executable})"
            )
    if evaluation.failures:
        lines.extend(f"[coverage] ERROR: {message}" for message in evaluation.failures)
    else:
        lines.append("[coverage] backend release thresholds satisfied.")
    return lines


def _pytest_executable() -> str:
    pytest_executable = ROOT_DIR / ".venv" / "bin" / "pytest"
    if pytest_executable.exists():
        return str(pytest_executable)
    return shutil.which("pytest") or "pytest"


def _load_report(report_json: str) -> dict[str, object]:
    return json.loads(Path(report_json).read_text())


def _print_lines(lines: list[str]) -> None:
    for line in lines:
        print(line, flush=True)


def main() -> int:
    args = _parse_args()
    os.chdir(ROOT_DIR)

    if args.report_json:
        evaluation = _evaluate_report(
            _load_report(args.report_json),
            min_total=args.min_total,
            report_limit=args.report_limit,
        )
        _print_lines(_format_evaluation_lines(evaluation))
        return 1 if evaluation.failures else 0

    temp_path = Path(tempfile.mkdtemp(prefix="trishul-coverage-"))
    coverage_file = temp_path / ".coverage"
    coverage_json = temp_path / "coverage.json"
    pytest_command = [
        _pytest_executable(),
        "-q",
        *args.tests,
        "--cov=backend/app",
        "--cov-report=term",
        f"--cov-report=json:{coverage_json}",
    ]
    env = os.environ.copy()
    env["COVERAGE_FILE"] = str(coverage_file)

    try:
        print("[coverage] running pytest with coverage", flush=True)
        for test_target in args.tests:
            print(f"[coverage] target {test_target}", flush=True)

        pytest_returncode = subprocess.run(
            pytest_command,
            cwd=ROOT_DIR,
            env=env,
            check=False,
        ).returncode

        if not coverage_json.exists():
            if pytest_returncode != 0:
                return pytest_returncode
            print(
                f"[coverage] ERROR: coverage JSON report was not generated at {coverage_json}.",
                flush=True,
            )
            return 1

        evaluation = _evaluate_report(
            _load_report(str(coverage_json)),
            min_total=args.min_total,
            report_limit=args.report_limit,
        )
        _print_lines(_format_evaluation_lines(evaluation))
        if pytest_returncode != 0:
            return pytest_returncode
        return 1 if evaluation.failures else 0
    finally:
        shutil.rmtree(temp_path, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
