from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timezone

from app.core.config import Settings, get_settings

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure_logging(settings_or_level: Settings | str | None = None) -> None:
    if isinstance(settings_or_level, Settings):
        settings = settings_or_level
        level_name = settings.log_level
    else:
        settings = get_settings()
        level_name = settings_or_level or settings.log_level

    log_level = getattr(logging, str(level_name).upper(), logging.INFO)
    log_path = settings.log_dir / "backend.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(LOG_FORMAT)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=2_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass

    root_logger.setLevel(log_level)
    root_logger.addHandler(stream_handler)
    root_logger.addHandler(file_handler)

    app_logger = logging.getLogger("app")
    app_logger.handlers = []
    app_logger.addHandler(stream_handler)
    app_logger.addHandler(file_handler)
    app_logger.setLevel(log_level)
    app_logger.propagate = False

    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"):
        named_logger = logging.getLogger(logger_name)
        named_logger.handlers = []
        named_logger.propagate = True
        named_logger.setLevel(log_level)

    logging.captureWarnings(True)
    logging.getLogger(__name__).info("Backend logging configured at %s", log_path)


def emit_backend_log(
    message: str,
    *,
    level: str = "INFO",
    logger_name: str = "app",
    settings: Settings | None = None,
) -> None:
    active_settings = settings or get_settings()
    log_path = active_settings.log_dir / "backend.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
    line = f"{timestamp} {level.upper()} {logger_name}: {message}"
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
    print(line, flush=True)
