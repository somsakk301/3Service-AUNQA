"""ChromaDB upsert storage for embedded chunks."""

import logging
import math
from collections.abc import Sequence
from typing import Any

import chromadb

from app.config import Settings
from app.vectorization.models import EmbeddedChunk

logger = logging.getLogger(__name__)

CHROMA_COLLECTION_NAME = "document_chunks"


class VectorStoreError(RuntimeError):
    """Raised when vector records are incomplete or cannot be stored."""


class ChromaVectorStore:
    """Store one document's traceable chunk vectors idempotently."""

    def __init__(
        self,
        settings: Settings,
        client: Any | None = None,
        *,
        collection_name: str = CHROMA_COLLECTION_NAME,
    ) -> None:
        self._dimension = settings.embedding_dimension
        self._client = client or chromadb.HttpClient(
            host=settings.chromadb_host,
            port=settings.chromadb_port,
        )
        self._collection = self._client.get_or_create_collection(
            name=collection_name
        )

    def upsert_document(self, records: Sequence[EmbeddedChunk]) -> int:
        if not records:
            raise VectorStoreError("At least one embedded chunk is required")
        ids = [record.id for record in records]
        if len(ids) != len(set(ids)):
            raise VectorStoreError("Chunk IDs must be unique")

        document_ids = {record.metadata.documentId for record in records}
        if len(document_ids) != 1:
            raise VectorStoreError("One ChromaDB write must contain one documentId")
        document_id = next(iter(document_ids))
        for record in records:
            if len(record.embedding) != self._dimension:
                raise VectorStoreError(
                    f"Embedding dimension must be {self._dimension}"
                )
            if not all(math.isfinite(value) for value in record.embedding):
                raise VectorStoreError("Embedding contains a non-finite value")
            metadata = record.metadata.to_dict()
            if not metadata.get("documentId") or not metadata.get("page"):
                raise VectorStoreError("documentId and page metadata are required")

        existing = self._collection.get(
            where={"documentId": document_id},
            include=[],
        )
        existing_ids = set(existing.get("ids") or [])
        self._collection.upsert(
            ids=ids,
            documents=[record.text for record in records],
            embeddings=[record.embedding for record in records],
            metadatas=[record.metadata.to_dict() for record in records],
        )
        stale_ids = sorted(existing_ids - set(ids))
        if stale_ids:
            self._collection.delete(ids=stale_ids)
        logger.info(
            "ChromaDB write completed documentId=%s chunks=%s staleDeleted=%s",
            document_id,
            len(records),
            len(stale_ids),
        )
        return len(records)

    def delete_document(self, document_id: str) -> None:
        self._collection.delete(where={"documentId": document_id})

    def get_document_ids(self, document_id: str) -> set[str]:
        result = self._collection.get(
            where={"documentId": document_id},
            include=[],
        )
        return set(result.get("ids") or [])
