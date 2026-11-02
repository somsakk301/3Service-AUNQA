"""Dense embedding adapter locked to FlagEmbedding BAAI/bge-m3."""

import logging
import math
from collections.abc import Sequence
from typing import Any, Protocol

from app.chunking.models import Chunk
from app.config import Settings
from app.vectorization.models import EmbeddedChunk

logger = logging.getLogger(__name__)


class EmbeddingError(RuntimeError):
    """Raised when BGE-M3 cannot produce valid 1024-dimensional vectors."""


class EmbeddingModel(Protocol):
    def encode(self, sentences: list[str], **kwargs: Any) -> Any: ...


class BgeM3Embedder:
    """Load the locked model lazily and embed only individual chunk text."""

    def __init__(
        self,
        settings: Settings,
        model: EmbeddingModel | None = None,
    ) -> None:
        if settings.embedding_model != "BAAI/bge-m3":
            raise EmbeddingError("Embedding model must remain BAAI/bge-m3")
        if settings.embedding_dimension != 1024:
            raise EmbeddingError("Embedding dimension must remain 1024")
        self._model_name = settings.embedding_model
        self._dimension = settings.embedding_dimension
        self._model = model

    def embed_chunks(
        self,
        chunks: Sequence[Chunk],
        *,
        batch_size: int = 8,
    ) -> list[EmbeddedChunk]:
        if not chunks:
            raise EmbeddingError("At least one chunk is required")
        if batch_size < 1:
            raise EmbeddingError("batch_size must be greater than zero")
        if any(not chunk.text for chunk in chunks):
            raise EmbeddingError("Chunk text must not be empty")
        if len({chunk.id for chunk in chunks}) != len(chunks):
            raise EmbeddingError("Chunk IDs must be unique")

        model = self._model or self._load_model()
        self._model = model
        logger.info(
            "Embedding started model=%s chunks=%s",
            self._model_name,
            len(chunks),
        )
        output = model.encode(
            [chunk.text for chunk in chunks],
            batch_size=batch_size,
            return_dense=True,
            return_sparse=False,
            return_colbert_vecs=False,
        )
        dense_vectors = output.get("dense_vecs") if isinstance(output, dict) else None
        if dense_vectors is None:
            raise EmbeddingError("BAAI/bge-m3 did not return dense_vecs")
        if hasattr(dense_vectors, "tolist"):
            dense_vectors = dense_vectors.tolist()
        if len(dense_vectors) != len(chunks):
            raise EmbeddingError("Embedding count does not match chunk count")

        results: list[EmbeddedChunk] = []
        for chunk, raw_vector in zip(chunks, dense_vectors, strict=True):
            vector = [float(value) for value in raw_vector]
            if len(vector) != self._dimension:
                raise EmbeddingError(
                    f"Embedding dimension must be {self._dimension}, got {len(vector)}"
                )
            if not all(math.isfinite(value) for value in vector):
                raise EmbeddingError("Embedding contains a non-finite value")
            results.append(
                EmbeddedChunk(
                    id=chunk.id,
                    text=chunk.text,
                    embedding=vector,
                    metadata=chunk.metadata,
                )
            )
        logger.info(
            "Embedding completed model=%s chunks=%s dimension=%s",
            self._model_name,
            len(results),
            self._dimension,
        )
        return results

    def _load_model(self) -> EmbeddingModel:
        try:
            from FlagEmbedding import BGEM3FlagModel
        except ImportError as exc:
            raise EmbeddingError("FlagEmbedding is not installed") from exc
        try:
            return BGEM3FlagModel(
                self._model_name,
                use_fp16=False,
                devices="cpu",
            )
        except Exception as exc:
            raise EmbeddingError("Unable to load BAAI/bge-m3") from exc
