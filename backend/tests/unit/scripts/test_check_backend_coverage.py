from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT_DIR = Path(__file__).resolve().parents[4]
MODULE_PATH = ROOT_DIR / "scripts" / "check_backend_coverage.py"
SPEC = importlib.util.spec_from_file_location(
    "trishul_check_backend_coverage",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
coverage_gate = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = coverage_gate
SPEC.loader.exec_module(coverage_gate)


def _configure_fake_backend_app(monkeypatch, tmp_path) -> dict[str, Path]:
    fake_root = tmp_path / "repo"
    app_dir = fake_root / "backend" / "app"
    files = {
        "api/routes_a.py": "API_ROUTE = 1\n",
        "services/bundles.py": "BUNDLES = 1\n",
        "services/runtime.py": "RUNTIME = 1\n",
        "db/connection.py": "DB = 1\n",
        "models/profile.py": "PROFILE = 1\n",
        "services/app_settings.py": "APP_SETTINGS = 1\n",
        "services/history.py": "HISTORY = 1\n",
        "services/session.py": "SESSION = 1\n",
    }
    resolved_files: dict[str, Path] = {}
    for relative_path, content in files.items():
        path = app_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        resolved_files[relative_path] = path

    monkeypatch.setattr(coverage_gate, "ROOT_DIR", fake_root)
    monkeypatch.setattr(coverage_gate, "BACKEND_APP_DIR", app_dir)
    monkeypatch.setattr(
        coverage_gate,
        "CRITICAL_SCOPES",
        (
            coverage_gate.CoverageScope(
                label="api",
                paths=(app_dir / "api",),
                minimum=90.0,
            ),
            coverage_gate.CoverageScope(
                label="bundles",
                paths=(app_dir / "services" / "bundles.py",),
                minimum=90.0,
            ),
            coverage_gate.CoverageScope(
                label="runtime",
                paths=(app_dir / "services" / "runtime.py",),
                minimum=90.0,
            ),
            coverage_gate.CoverageScope(
                label="persistence",
                paths=(
                    app_dir / "db",
                    app_dir / "models",
                    app_dir / "services" / "app_settings.py",
                    app_dir / "services" / "history.py",
                    app_dir / "services" / "session.py",
                ),
                minimum=90.0,
            ),
        ),
    )
    return resolved_files


def test_evaluate_report_flags_scope_failures_and_orders_lowest_files(
    monkeypatch,
    tmp_path,
):
    files = _configure_fake_backend_app(monkeypatch, tmp_path)
    report = {
        "files": {
            str(files["api/routes_a.py"]): {
                "summary": {"covered_lines": 8, "num_statements": 10}
            },
            str(files["services/bundles.py"]): {
                "summary": {"covered_lines": 18, "num_statements": 20}
            },
            str(files["services/runtime.py"]): {
                "summary": {"covered_lines": 8, "num_statements": 10}
            },
            str(files["db/connection.py"]): {
                "summary": {"covered_lines": 10, "num_statements": 10}
            },
            str(files["models/profile.py"]): {
                "summary": {"covered_lines": 10, "num_statements": 10}
            },
            str(files["services/app_settings.py"]): {
                "summary": {"covered_lines": 9, "num_statements": 10}
            },
            str(files["services/history.py"]): {
                "summary": {"covered_lines": 7, "num_statements": 10}
            },
            str(files["services/session.py"]): {
                "summary": {"covered_lines": 9, "num_statements": 10}
            },
        }
    }

    evaluation = coverage_gate._evaluate_report(report, min_total=85.0, report_limit=3)

    assert evaluation.failures == (
        "api coverage 80.0% is below 90.0%.",
        "runtime coverage 80.0% is below 90.0%.",
    )
    assert [detail.path.name for detail in evaluation.lowest_files] == [
        "history.py",
        "routes_a.py",
        "runtime.py",
    ]


def test_format_evaluation_lines_reports_success_when_thresholds_pass(
    monkeypatch,
    tmp_path,
):
    files = _configure_fake_backend_app(monkeypatch, tmp_path)
    report = {
        "files": {
            str(path): {"summary": {"covered_lines": 10, "num_statements": 10}}
            for path in files.values()
        }
    }

    evaluation = coverage_gate._evaluate_report(report, min_total=85.0, report_limit=2)
    lines = coverage_gate._format_evaluation_lines(evaluation)

    assert evaluation.failures == ()
    assert lines[-1] == "[coverage] backend release thresholds satisfied."
    assert all("ERROR" not in line for line in lines)
