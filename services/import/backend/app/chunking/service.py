"""Locked 500-character page chunking with 100-character overlap."""

import logging
from collections.abc import Mapping, Sequence

from bson import ObjectId
from bson.errors import InvalidId

from app.chunking.models import Chunk, ChunkMetadata, DocumentType, PageContext
from app.config import Settings
from app.extraction.models import ExtractedPage
from app.parsing.normalization import clean_text, normalize_string

logger = logging.getLogger(__name__)

_DOCUMENT_TYPES = {"curriculum", "cv", "appointment"}


class ChunkingError(ValueError):
    """Raised when a document cannot produce valid, traceable chunks."""


class DocumentChunker:
    """Create deterministic chunks while retaining each physical/logical page."""

    def __init__(self, settings: Settings) -> None:
        self._chunk_size = settings.chunk_size
        self._chunk_overlap = settings.chunk_overlap
        if self._chunk_size != 500 or self._chunk_overlap != 100:
            raise ChunkingError("Chunk settings must remain locked to 500/100")
        self._step = self._chunk_size - self._chunk_overlap

    def chunk_document(
        self,
        *,
        document_id: ObjectId | str,
        curriculum_id: ObjectId | str,
        document_type: str,
        pages: Sequence[ExtractedPage],
        page_contexts: Mapping[int, PageContext] | None = None,
    ) -> list[Chunk]:
        document_id_text = self._object_id_text(document_id, "documentId")
        curriculum_id_text = self._object_id_text(curriculum_id, "curriculumId")
        if document_type not in _DOCUMENT_TYPES:
            raise ChunkingError(
                "documentType must be curriculum, cv, or appointment"
            )

        page_numbers = [page.pageNumber for page in pages]
        if any(page_number < 1 for page_number in page_numbers):
            raise ChunkingError("pageNumber must be greater than zero")
        if len(page_numbers) != len(set(page_numbers)):
            raise ChunkingError("pageNumber must be unique within a document")

        contexts = page_contexts or {}
        unknown_context_pages = set(contexts) - set(page_numbers)
        if unknown_context_pages:
            raise ChunkingError("page context references an unknown pageNumber")

        chunks: list[Chunk] = []
        for page in sorted(pages, key=lambda item: item.pageNumber):
            text = clean_text(page.text)
            if not text:
                continue
            context = self._validated_context(contexts.get(page.pageNumber))
            for chunk_index, chunk_text in enumerate(
                self._split_text(text),
                start=1,
            ):
                metadata = ChunkMetadata(
                    documentId=document_id_text,
                    curriculumId=curriculum_id_text,
                    documentType=document_type,  # type: ignore[arg-type]
                    page=page.pageNumber,
                    chunkIndex=chunk_index,
                    section=context.section if context else None,
                    personId=context.personId if context else None,
                )
                chunks.append(
                    Chunk(
                        id=(
                            f"{document_id_text}-p{page.pageNumber}"
                            f"-c{chunk_index:02d}"
                        ),
                        text=chunk_text,
                        metadata=metadata,
                    )
                )

        if not chunks:
            raise ChunkingError("Document contains no chunkable text")
        if len({chunk.id for chunk in chunks}) != len(chunks):
            raise ChunkingError("Chunk ID must be unique")
        logger.info(
            "Chunking completed documentId=%s pages=%s chunks=%s",
            document_id_text,
            len(pages),
            len(chunks),
        )
        return chunks

    def _split_text(self, text: str) -> list[str]:
        chunks: list[str] = []
        start = 0
        while start < len(text):
            end = min(start + self._chunk_size, len(text))
            chunks.append(text[start:end])
            if end == len(text):
                break
            start += self._step
        return chunks

    def _validated_context(self, context: PageContext | None) -> PageContext | None:
        if context is None:
            return None
        normalized_section = (
            normalize_string(context.section) if context.section else ""
        )
        section = normalized_section or None
        person_id = (
            self._object_id_text(context.personId, "personId")
            if context.personId is not None
            else None
        )
        return PageContext(section=section, personId=person_id)

    @staticmethod
    def _object_id_text(value: ObjectId | str, field_name: str) -> str:
        try:
            return str(value if isinstance(value, ObjectId) else ObjectId(value))
        except (InvalidId, TypeError) as exc:
            raise ChunkingError(f"{field_name} must be a valid ObjectId") from exc
