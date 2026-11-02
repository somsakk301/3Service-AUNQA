"""Read-only access to Source Data owned by the Data Import side.

The repository is backend-neutral: queries are `SourceQuery` values and only a
`SourceDataAdapter` knows how to run them against a concrete store. It never
decides PASS / FAIL / REVIEW / N/A.
"""
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, Sequence

from app.models.source_schema import SOURCE_SCHEMA
from app.repositories.base import Document

# Source collections named by the Data Schema. Configuration (`ps_requirements`) is NOT among them.
SOURCE_COLLECTIONS = frozenset(SOURCE_SCHEMA)


class UnknownSourceCollection(KeyError):
    pass


@dataclass(frozen=True)
class SourceQuery:
    equals: Mapping[str, Any] = field(default_factory=dict)
    any_of: Mapping[str, Sequence[Any]] = field(default_factory=dict)


class SourceDataAdapter(Protocol):
    def find(self, collection: str, query: SourceQuery) -> list[Document]: ...


class SourceDataRepository:
    def __init__(self, adapter: SourceDataAdapter) -> None:
        self._adapter = adapter

    def find(self, collection: str, query: SourceQuery | None = None) -> list[Document]:
        if collection not in SOURCE_COLLECTIONS:
            raise UnknownSourceCollection(f"'{collection}' is not a source data collection")
        return self._adapter.find(collection, query or SourceQuery())

    def find_curricula(self, curriculum_code: str | None = None) -> list[Document]:
        query = SourceQuery(equals={"curriculumCode": curriculum_code} if curriculum_code else {})
        return self.find("curricula", query)
