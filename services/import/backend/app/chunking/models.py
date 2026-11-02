"""Chunk and metadata models matching SRS sections 29-30."""

from dataclasses import dataclass
from typing import Any, Literal


DocumentType = Literal["curriculum", "cv", "appointment"]


@dataclass(frozen=True)
class PageContext:
    """Optional metadata used only when the source page can be identified."""

    section: str | None = None
    personId: str | None = None


@dataclass(frozen=True)
class ChunkMetadata:
    documentId: str
    curriculumId: str
    documentType: DocumentType
    page: int
    chunkIndex: int
    section: str | None = None
    personId: str | None = None

    def to_dict(self) -> dict[str, str | int]:
        """Return Chroma-compatible scalar metadata, omitting unknown context."""
        result: dict[str, str | int] = {
            "documentId": self.documentId,
            "curriculumId": self.curriculumId,
            "documentType": self.documentType,
            "page": self.page,
            "chunkIndex": self.chunkIndex,
        }
        if self.section is not None:
            result["section"] = self.section
        if self.personId is not None:
            result["personId"] = self.personId
        return result


@dataclass(frozen=True)
class Chunk:
    id: str
    text: str
    metadata: ChunkMetadata

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "metadata": self.metadata.to_dict(),
        }
