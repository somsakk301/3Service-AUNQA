"""Evidence: the source documents of the monitored curriculum, read as stored.

A document belongs to a curriculum through `documents.curriculumId -> curricula._id` (Data Dictionary);
nothing links a document to a single PS, so every PS result of the curriculum shows the same documents
(project owner, 2026-09-26). Evidence is read only: it is not traceability (the engine does not read
documents), it never changes a status, and a missing value is reported as missing, never filled in.
"""
from typing import Any

from app.models.schemas import EvidenceItem
from app.models.source_schema import CURRICULUM_KEY, CURRICULUM_LINK
from app.repositories.base import Document
from app.repositories.source_data import SourceDataRepository, SourceQuery

COLLECTION = "documents"
_ORIGINAL = "originalFile"


def _text(value: Any) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _item(doc: Document) -> EvidenceItem:
    reference = str(doc.get("_id"))
    original = doc.get(_ORIGINAL)
    original = original if isinstance(original, dict) else {}
    return EvidenceItem(label=_text(doc.get("fileName")) or reference, reference=reference,
                        storage=_text(original.get("storage")), path=_text(original.get("path")))


def evidence_of(curriculum: Document, source: SourceDataRepository) -> list[EvidenceItem]:
    """One item per document of the curriculum, in the order the source returns them."""
    query = SourceQuery(equals={CURRICULUM_LINK[COLLECTION]: curriculum.get(CURRICULUM_KEY)})
    items = {}
    for doc in source.find(COLLECTION, query):
        item = _item(doc)
        items.setdefault(item.reference, item)
    return list(items.values())
