from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


def test_emit_backend_log_writes_file_when_stdout_and_file_enabled(monkeypatch, tmp_path):
    from app.core.config import get_settings, reset_settings_cache
    from app.core.logging import configure_logging, emit_backend_log

    monkeypatch.setenv("TRISHUL_DATA_DIR", str(tmp_path / "app-data"))
    monkeypatch.setenv("LOG_DESTINATION", "stdout+file")
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    reset_settings_cache()
    settings = get_settings()

    assert settings.log_destination == "stdout+file"
    assert settings.file_logging_enabled is True
    assert settings.stdout_logging_enabled is True

    configure_logging(settings)
    emit_backend_log("visible info", logger_name="test.emit_backend_log", settings=settings)
    emit_backend_log(
        "hidden debug",
        level="DEBUG",
        logger_name="test.emit_backend_log",
        settings=settings,
    )

    backend_log = Path(settings.log_dir / "backend.log").read_text(encoding="utf-8")
    assert "visible info" in backend_log
    assert "hidden debug" not in backend_log

    reset_settings_cache()


def test_emit_backend_log_uses_stdout_only_in_container(monkeypatch, tmp_path, capsys):
    from app.core.config import get_settings, reset_settings_cache
    from app.core.logging import configure_logging, emit_backend_log

    monkeypatch.setenv("TRISHUL_DATA_DIR", str(tmp_path / "app-data"))
    monkeypatch.setenv("TRISHUL_CONTAINER", "1")
    monkeypatch.delenv("LOG_DESTINATION", raising=False)
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    reset_settings_cache()
    settings = get_settings()

    assert settings.log_destination == "stdout"
    assert settings.file_logging_enabled is False
    assert settings.stdout_logging_enabled is True
    assert not settings.log_dir.exists()

    configure_logging(settings)
    capsys.readouterr()

    emit_backend_log("visible stdout", logger_name="test.emit_backend_log", settings=settings)
    emit_backend_log(
        "hidden debug",
        level="DEBUG",
        logger_name="test.emit_backend_log",
        settings=settings,
    )

    captured = capsys.readouterr()
    assert "visible stdout" in captured.out
    assert "hidden debug" not in captured.out
    assert not settings.log_file.exists()

    reset_settings_cache()


def test_configure_logging_can_skip_announcement(monkeypatch, tmp_path, capsys):
    from app.core.config import get_settings, reset_settings_cache
    from app.core.logging import configure_logging

    monkeypatch.setenv("TRISHUL_DATA_DIR", str(tmp_path / "app-data"))
    monkeypatch.setenv("TRISHUL_CONTAINER", "1")
    monkeypatch.delenv("LOG_DESTINATION", raising=False)
    reset_settings_cache()
    settings = get_settings()

    capsys.readouterr()
    configure_logging(settings, announce=False)
    captured = capsys.readouterr()
    assert "Backend logging configured" not in captured.out

    reset_settings_cache()


def test_settings_remove_stale_file_logs_when_stdout_only(monkeypatch, tmp_path):
    from app.core.config import get_settings, reset_settings_cache

    data_dir = tmp_path / "app-data"
    log_dir = data_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "backend.log").write_text("stale\n", encoding="utf-8")
    (log_dir / "backend.log.1").write_text("stale rotated\n", encoding="utf-8")

    monkeypatch.setenv("TRISHUL_DATA_DIR", str(data_dir))
    monkeypatch.setenv("TRISHUL_CONTAINER", "1")
    monkeypatch.delenv("LOG_DESTINATION", raising=False)
    reset_settings_cache()

    settings = get_settings()
    assert settings.log_destination == "stdout"
    assert not settings.log_file.exists()
    assert not settings.log_dir.exists()

    reset_settings_cache()


def test_configure_logging_honors_file_only_destination(monkeypatch, tmp_path):
    from app.core.config import get_settings, reset_settings_cache
    from app.core.logging import configure_logging

    monkeypatch.setenv("TRISHUL_DATA_DIR", str(tmp_path / "app-data"))
    monkeypatch.setenv("LOG_DESTINATION", "file")
    reset_settings_cache()
    settings = get_settings()

    assert settings.log_destination == "file"
    assert settings.file_logging_enabled is True
    assert settings.stdout_logging_enabled is False

    configure_logging(settings)

    handlers = logging.getLogger().handlers
    assert len(handlers) == 1
    assert isinstance(handlers[0], RotatingFileHandler)

    reset_settings_cache()


def test_configure_logging_sets_explicit_operational_loggers(monkeypatch, tmp_path):
    from app.core.config import get_settings, reset_settings_cache
    from app.core.logging import configure_logging

    monkeypatch.setenv("TRISHUL_DATA_DIR", str(tmp_path / "app-data"))
    monkeypatch.setenv("LOG_DESTINATION", "stdout+file")
    reset_settings_cache()
    settings = get_settings()

    configure_logging(settings)

    for logger_name in ("app", "app.http", "app.operations", "app.runtime"):
        logger = logging.getLogger(logger_name)
        assert logger.handlers
        assert logger.propagate is False

    expected_levels = {
        "uvicorn": logging.INFO,
        "uvicorn.error": logging.INFO,
        "uvicorn.access": logging.WARNING,
        "fastapi": logging.WARNING,
    }
    for logger_name, expected_level in expected_levels.items():
        logger = logging.getLogger(logger_name)
        assert logger.level == expected_level
        assert logger.propagate is True

    reset_settings_cache()


def test_uvicorn_lifecycle_filter_keeps_lifecycle_and_drops_websocket_noise():
    from app.core.logging import _UvicornLifecycleFilter

    lifecycle_filter = _UvicornLifecycleFilter()

    startup_record = logging.LogRecord(
        name="uvicorn.error",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="Started server process [1]",
        args=(),
        exc_info=None,
    )
    websocket_record = logging.LogRecord(
        name="uvicorn.error",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg='127.0.0.1:12345 - "WebSocket /api/ws" [accepted]',
        args=(),
        exc_info=None,
    )
    error_record = logging.LogRecord(
        name="uvicorn.error",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="Socket failed",
        args=(),
        exc_info=None,
    )

    assert lifecycle_filter.filter(startup_record) is True
    assert lifecycle_filter.filter(websocket_record) is False
    assert lifecycle_filter.filter(error_record) is True
