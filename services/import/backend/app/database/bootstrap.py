"""Idempotent MongoDB collection, validator, and index bootstrap."""

import json
import logging
from typing import Any

from pymongo.database import Database
from pymongo.errors import CollectionInvalid

from app.config import get_settings
from app.connections import ServiceConnections
from app.database.schema import COLLECTION_SPECS
from app.logging_config import configure_logging

logger = logging.getLogger(__name__)


def ensure_database_schema(
    database: Database[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Create allowed collections and apply locked validators/indexes."""

    existing_collections = set(database.list_collection_names())
    result: dict[str, dict[str, Any]] = {}

    for collection_name, spec in COLLECTION_SPECS.items():
        created = False
        if collection_name not in existing_collections:
            try:
                database.create_collection(
                    collection_name,
                    validator={"$jsonSchema": spec.schema},
                    validationLevel="strict",
                    validationAction="error",
                )
                created = True
            except CollectionInvalid:
                # Another backend instance may have created it concurrently.
                pass

        database.command(
            {
                "collMod": collection_name,
                "validator": {"$jsonSchema": spec.schema},
                "validationLevel": "strict",
                "validationAction": "error",
            }
        )
        index_names = database[collection_name].create_indexes(list(spec.indexes))
        result[collection_name] = {
            "created": created,
            "indexes": index_names,
        }
        logger.info(
            "MongoDB schema ready collection=%s created=%s indexes=%s",
            collection_name,
            created,
            index_names,
        )

    return result


def main() -> int:
    settings = get_settings()
    configure_logging(settings.log_level)
    connections = ServiceConnections(settings)
    try:
        connections.check_mongodb()
        result = ensure_database_schema(connections.mongodb_database)
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception:
        logger.exception("MongoDB schema bootstrap failed")
        return 1
    finally:
        connections.close()


if __name__ == "__main__":
    raise SystemExit(main())

