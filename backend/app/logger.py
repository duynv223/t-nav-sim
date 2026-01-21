from __future__ import annotations

import logging.config
import os


def configure_logging() -> None:
    level = (os.environ.get("SIM_LOG_LEVEL") or os.environ.get("LOG_LEVEL") or "INFO").upper()
    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s %(levelname)s %(name)s: %(message)s",
                "datefmt": "%H:%M:%S",
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default",
                "stream": "ext://sys.stdout",
            }
        },
        "root": {"handlers": ["console"], "level": level},
        "loggers": {
            "uvicorn.error": {"level": level},
            "uvicorn.access": {"level": level},
            "sim.api": {"level": level},
        },
    }
    logging.config.dictConfig(config)
