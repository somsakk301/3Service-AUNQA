"""Read-only access to PS Configuration owned by the Data Import / configuration side."""
from typing import Protocol

from app.repositories.base import Document

# Marks a document of the configuration collection that is not a PS configuration (project owner,
# 2026-09-26). Such a document is never evaluated as a PS.
CONFIG_TYPE_KEY = "configType"


class ConfigurationAdapter(Protocol):
    def read_active(self) -> list[Document]: ...

    def read_by_code(self, ps_code: str) -> Document | None: ...

    def read_by_type(self, config_type: str) -> list[Document]: ...


def _is_ps_configuration(doc: Document) -> bool:
    return CONFIG_TYPE_KEY not in doc


class ConfigurationRepository:
    """Returns configuration documents as stored. It holds no rule of its own."""

    def __init__(self, adapter: ConfigurationAdapter) -> None:
        self._adapter = adapter

    def load_active_requirements(self) -> list[Document]:
        docs = [d for d in self._adapter.read_active() if _is_ps_configuration(d) and d.get("active") is True]
        return sorted(docs, key=lambda d: str(d.get("psCode", "")))

    def get_requirement(self, ps_code: str) -> Document | None:
        doc = self._adapter.read_by_code(ps_code)
        return doc if doc is not None and _is_ps_configuration(doc) and doc.get("active") is True else None

    def load_by_type(self, config_type: str) -> list[Document]:
        """Every document of one configType, as stored: none, one, or duplicates for the caller to report."""
        return self._adapter.read_by_type(config_type)
