"""Vector record passed from BGE-M3 to ChromaDB."""

from dataclasses import dataclass

from app.chunking.models import ChunkMetadata


@dataclass(frozen=True)
class EmbeddedChunk:
    id: str
    text: str
    embedding: list[float]
    metadata: ChunkMetadata
