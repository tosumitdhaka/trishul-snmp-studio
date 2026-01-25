import logging
import logging.config
import sys
from core.config import settings

def setup_logging():
    """
    Configures logging using dictConfig.
    - format: [Timestamp] [Level] [Module] - Message
    - handlers: Console (stdout)
    - loggers: Root, Uvicorn, FastAPI
    """
    
    log_level = settings.LOG_LEVEL.upper()
    
    LOGGING_CONFIG = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": "[%(asctime)s] %(levelname)-8s %(name)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "standard",
                "stream": "ext://sys.stdout",
            },
        },
        "loggers": {
            # The Root Logger (catches your app logs)
            "": {
                "handlers": ["console"],
                "level": log_level,
                "propagate": True
            },
            # Uvicorn (Server logs) - Override to match our format
            "uvicorn": {
                "handlers": ["console"],
                "level": "INFO", 
                "propagate": False
            },
            "uvicorn.access": {
                "handlers": ["console"],
                "level": "INFO",
                "propagate": False
            },
            "uvicorn.error": {
                "handlers": ["console"],
                "level": "INFO",
                "propagate": False
            },
        }
    }

    logging.config.dictConfig(LOGGING_CONFIG)
