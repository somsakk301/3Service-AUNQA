"""CLI entry point for running Phase 4 on one existing document."""

import argparse
import json
import logging

from app.config import get_settings
from app.connections import ServiceConnections
from app.extraction.service import DocumentExtractionService
from app.logging_config import configure_logging

logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract one Import Service document")
    parser.add_argument("document_id")
    arguments = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)
    connections = ServiceConnections(settings)
    try:
        connections.check_mongodb()
        result = DocumentExtractionService(
            settings,
            connections.mongodb_database,
        ).process_document(arguments.document_id)
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception:
        logger.exception("Document extraction command failed")
        return 1
    finally:
        connections.close()


if __name__ == "__main__":
    raise SystemExit(main())

