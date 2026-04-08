import logging
import logging.config

from app.core.config import get_settings


def setup_logging() -> None:
    settings = get_settings()
    log_level = "DEBUG" if settings.debug else "INFO"

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                    "datefmt": "%Y-%m-%d %H:%M:%S",
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                    "level": log_level,
                }
            },
            "loggers": {
                "app": {"handlers": ["console"], "level": log_level, "propagate": False},
                "uvicorn": {"handlers": ["console"], "level": log_level, "propagate": False},
                "uvicorn.error": {
                    "handlers": ["console"],
                    "level": log_level,
                    "propagate": False,
                },
                "uvicorn.access": {
                    "handlers": ["console"],
                    "level": log_level,
                    "propagate": False,
                },
            },
            "root": {"handlers": ["console"], "level": log_level},
        }
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
