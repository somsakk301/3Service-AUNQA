from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Iterable

from app.models.schemas import TraceItem
from app.models.source_schema import DISPLAY_FIELD, REFERENCES
from app.monitoring.helpers import ConfigError, display, get_path, is_blank, is_hashable
from app.monitoring.manual import ManualResultSource, NoManualResults
from app.monitoring.reference import ReferenceSource
from app.repositories.base import Document
from app.repositories.source_data import SourceDataRepository, SourceQuery, UnknownSourceCollection


def name_of(names: dict[Any, str], value: Any) -> str:
    """The display name of `value` from a `names()` result, or the value itself."""
    return names.get(value, display(value)) if is_hashable(value) else display(value)


@dataclass
class EvaluationContext:
    curriculum: Document
    source: SourceDataRepository
    references: ReferenceSource
    manual: ManualResultSource = field(default_factory=NoManualResults)
    _trace: dict[tuple[str, str], dict[str, str]] = field(default_factory=dict)
    _names: dict[tuple[str, Any], Any] = field(default_factory=dict)

    def find(self, collection: str, query: SourceQuery, fields: tuple[str, ...] = ()) -> list[Document]:
        try:
            records = self.source.find(collection, query)
        except UnknownSourceCollection as exc:
            raise ConfigError(str(exc)) from exc
        for rec in records:
            self.touch(collection, rec, fields)
        return records

    def touch(self, collection: str, record: Document, fields: tuple[str, ...]) -> None:
        """Record that `record` was read and which of its fields were used (traceability)."""
        seen = self._trace.setdefault((collection, str(record.get("_id", "?"))), {})
        seen.update({f: display(get_path(record, f)) for f in fields})

    def names(self, ref_field: str, values: Iterable[Any]) -> dict[Any, str]:
        """Display names for values of a reference field (the Data Schema's REFERENCES / DISPLAY_FIELD).

        DISPLAY ONLY: the lookup is not recorded in traceability (it is not evidence) and no evaluation
        reads it. A value whose record or name is missing is shown as the value plus what is missing; two
        values with the same name are told apart by their values. Other fields get no names ({}).
        """
        target = REFERENCES.get(ref_field)
        name_field = DISPLAY_FIELD.get(target[0]) if target else None
        if target is None or name_field is None:
            return {}
        collection, key = target
        wanted = list(dict.fromkeys(v for v in values if not is_blank(v) and is_hashable(v)))
        unknown = [v for v in wanted if (ref_field, v) not in self._names]
        if unknown:
            found: dict[Any, Any] = {}
            for rec in self.source.find(collection, SourceQuery(any_of={key: tuple(unknown)})):
                k = get_path(rec, key)
                if is_hashable(k):
                    found.setdefault(k, get_path(rec, name_field))
            for v in unknown:
                self._names[(ref_field, v)] = found.get(v)
        raw = {v: self._names[(ref_field, v)] for v in wanted}
        repeated = Counter(display(n) for n in raw.values() if not is_blank(n))
        out: dict[Any, str] = {}
        for v, n in raw.items():
            if is_blank(n):
                out[v] = f"{display(v)} (ไม่พบ {collection}.{name_field})"
            elif repeated[display(n)] > 1:
                out[v] = f"{display(n)} ({display(v)})"
            else:
                out[v] = display(n)
        return out

    def reset_trace(self) -> None:
        self._trace.clear()

    @property
    def found_count(self) -> int:
        return len(self._trace)

    def trace_items(self) -> list[TraceItem]:
        return [TraceItem(collection=c, record_id=rid, fields=sorted(v), values=v) for (c, rid), v in self._trace.items()]
