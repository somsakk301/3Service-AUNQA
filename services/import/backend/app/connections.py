"""MongoDB and ChromaDB connection management."""

import logging
from typing import Any

import chromadb
from pymongo import MongoClient
from pymongo.database import Database

from app.config import Settings

logger = logging.getLogger(__name__)


class ServiceConnections:
    """Own the database clients used by the backend process."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._mongodb = MongoClient(
            settings.mongodb_uri,
            serverSelectionTimeoutMS=settings.connection_timeout_ms,
            connectTimeoutMS=settings.connection_timeout_ms,
        )
        self._chromadb: Any | None = None

    def check_mongodb(self) -> dict[str, Any]:
        """Ping MongoDB and return a non-sensitive status payload."""

        response = self._mongodb.admin.command("ping")
        if response.get("ok") != 1.0:
            raise ConnectionError("MongoDB ping did not return ok=1")
        logger.info("MongoDB connection verified", extra={"event": "mongodb_connection"})
        return {"status": "ok", "ping": response["ok"]}

    @property
    def mongodb_database(self) -> Database[dict[str, Any]]:
        """Return the application database selected by MONGODB_URI."""

        return self._mongodb.get_default_database()

    def check_chromadb(self) -> dict[str, Any]:
        """Call the ChromaDB heartbeat through its HTTP client."""

        if self._chromadb is None:
            self._chromadb = chromadb.HttpClient(
                host=self._settings.chromadb_host,
                port=self._settings.chromadb_port,
            )
        heartbeat = self._chromadb.heartbeat()
        logger.info("ChromaDB connection verified", extra={"event": "chromadb_connection"})
        return {"status": "ok", "heartbeat": heartbeat}

    def check_all(self) -> dict[str, dict[str, Any]]:
        """Verify both required data services."""

        return {
            "mongodb": self.check_mongodb(),
            "chromadb": self.check_chromadb(),
        }

    def close(self) -> None:
        """Release resources owned by clients that expose a close operation."""

        self._mongodb.close()
        logger.info("Database connections closed", extra={"event": "shutdown"})
