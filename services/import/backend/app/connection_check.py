"""Command-line connection check for container verification."""

import json
import logging

from app.config import get_settings
from app.connections import ServiceConnections
from app.logging_config import configure_logging

logger = logging.getLogger(__name__)


def main() -> int:
    settings = get_settings()
    configure_logging(settings.log_level)
    connections = ServiceConnections(settings)
    try:
        result = connections.check_all()
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception:
        logger.exception("Database connection verification failed", extra={"event": "error"})
        return 1
    finally:
        connections.close()


if __name__ == "__main__":
    raise SystemExit(main())

