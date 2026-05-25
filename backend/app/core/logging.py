from __future__ import annotations

from datetime import datetime, timezone
import logging
from logging.handlers import RotatingFileHandler

from app.core.config import Settings, get_settings

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
_UVICORN_LIFECYCLE_PREFIXES = (
    "Started server process",
    "Waiting for application startup.",
    "Application startup complete.",
    "Uvicorn running on",
    "Shutting down",
    "Waiting for application shutdown.",
    "Application shutdown complete.",
    "Finished server process",
)


class _UvicornLifecycleFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if record.levelno >= logging.WARNING:
            return True
        message = record.getMessage()
        return any(message.startswith(prefix) for prefix in _UVICORN_LIFECYCLE_PREFIXES)


def configure_logging(
    settings_or_level: Settings | str | None = None,
    *,
    announce: bool = True,
) -> None:
    if isinstance(settings_or_level, Settings):
        settings = settings_or_level
        level_name = settings.log_level
    else:
        settings = get_settings()
        level_name = settings_or_level or settings.log_level

    log_level = getattr(logging, str(level_name).upper(), logging.INFO)

    formatter = logging.Formatter(LOG_FORMAT)

    handlers: list[logging.Handler] = []
    if settings.stdout_logging_enabled:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        handlers.append(stream_handler)
    if settings.file_logging_enabled:
        log_path = settings.log_file
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=2_000_000,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)

    root_logger = logging.getLogger()
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass

    root_logger.setLevel(log_level)
    for handler in handlers:
        root_logger.addHandler(handler)

    for logger_name in ("app", "app.http", "app.operations", "app.runtime"):
        named_app_logger = logging.getLogger(logger_name)
        named_app_logger.handlers = []
        for handler in handlers:
            named_app_logger.addHandler(handler)
        named_app_logger.setLevel(log_level)
        named_app_logger.propagate = False

    uvicorn_levels = {
        "uvicorn": logging.INFO,
        "uvicorn.error": logging.INFO,
        "uvicorn.access": logging.WARNING,
        "fastapi": logging.WARNING,
    }
    for logger_name, logger_level in uvicorn_levels.items():
        named_logger = logging.getLogger(logger_name)
        named_logger.handlers = []
        named_logger.filters = []
        named_logger.propagate = True
        named_logger.setLevel(logger_level)
        if logger_name in {"uvicorn", "uvicorn.error"}:
            named_logger.addFilter(_UvicornLifecycleFilter())

    logging.captureWarnings(True)
    if announce:
        if settings.file_logging_enabled:
            logging.getLogger(__name__).info("Backend logging configured at %s", settings.log_file)
        else:
            logging.getLogger(__name__).info(
                "Backend logging configured for stdout/stderr only"
            )


def emit_backend_log(
    message: str,
    *,
    level: str | int = "INFO",
    logger_name: str = "app",
    settings: Settings | None = None,
) -> None:
    active_settings = settings or get_settings()
    if isinstance(level, int):
        level_no = level
    else:
        level_name = str(level).upper()
        level_no = getattr(logging, level_name, logging.INFO)
    configured_level = getattr(logging, str(active_settings.log_level).upper(), logging.INFO)
    if level_no < configured_level:
        return

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
    level_name = logging.getLevelName(level_no)
    line = f"{timestamp} {level_name} {logger_name}: {message}"
    if active_settings.file_logging_enabled:
        log_path = active_settings.log_file
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    if active_settings.stdout_logging_enabled:
        print(line, flush=True)
