"""Central logging setup for the Import Service."""

import logging
from logging.config import dictConfig


def configure_logging(level: str) -> None:
    """Configure consistent stdout logging for the backend container."""

    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
                    "datefmt": "%Y-%m-%dT%H:%M:%S%z",
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                    "stream": "ext://sys.stdout",
                }
            },
            "root": {
                "handlers": ["console"],
                "level": level,
            },
        }
    )
    logging.getLogger(__name__).info("Logging configured", extra={"event": "startup"})

