"""MongoDB adapters for the Data Import side (read-only: only `find` is ever called).

Source Data and Configuration are separate adapters, so they may live in
different databases.
"""
from typing import Any

from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import ConnectionFailure, PyMongoError

from app.repositories.base import DataSourceConnectionError, DataSourceError, Document
from app.repositories.configuration import CONFIG_TYPE_KEY
from app.repositories.source_data import SourceQuery

CONFIGURATION_COLLECTION = "ps_requirements"  # Data Dictionary


def connect(uri: str, db_name: str) -> Database:
    return MongoClient(uri, serverSelectionTimeoutMS=3000)[db_name]


def _read(database: Database, collection: str, query: dict[str, Any]) -> list[Document]:
    try:
        return list(database[collection].find(query))
    except PyMongoError as exc:
        raise source_error(exc) from exc


def source_error(exc: PyMongoError) -> DataSourceError:
    """Unreachable database -> DataSourceConnectionError; any other driver error -> DataSourceError (both: 503)."""
    return (DataSourceConnectionError if isinstance(exc, ConnectionFailure) else DataSourceError)(str(exc))


class MongoSourceDataAdapter:
    def __init__(self, database: Database) -> None:
        self._db = database

    def find(self, collection: str, query: SourceQuery) -> list[Document]:
        native: dict[str, Any] = dict(query.equals)
        native.update({field: {"$in": list(values)} for field, values in query.any_of.items()})
        return _read(self._db, collection, native)


class MongoConfigurationAdapter:
    def __init__(self, database: Database) -> None:
        self._db = database

    def read_active(self) -> list[Document]:
        return _read(self._db, CONFIGURATION_COLLECTION, {"active": True})

    def read_by_code(self, ps_code: str) -> Document | None:
        found = _read(self._db, CONFIGURATION_COLLECTION, {"psCode": ps_code})
        return found[0] if found else None

    def read_by_type(self, config_type: str) -> list[Document]:
        return _read(self._db, CONFIGURATION_COLLECTION, {CONFIG_TYPE_KEY: config_type})
