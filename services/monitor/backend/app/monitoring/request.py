"""The generic execution request produced by the interpreter and run by the engine."""
from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class Comparison:
    operator: str
    value: Any


@dataclass(frozen=True)
class Selection:
    """FILTER: the records of `collection` whose fields equal / are among the configured values."""
    collection: str
    equals: Mapping[str, Any] = field(default_factory=dict)
    any_of: Mapping[str, tuple] = field(default_factory=dict)


@dataclass(frozen=True)
class Lookup:
    """JOIN: records of `collection` related to a subject through `pairs` (subject field, lookup field)."""
    collection: str
    pairs: tuple[tuple[str, str], ...]
    equals: Mapping[str, Any] = field(default_factory=dict)
    any_of: Mapping[str, tuple] = field(default_factory=dict)


@dataclass(frozen=True)
class Window:
    """TIME WINDOW over an integer year field: reference - years <= value <= reference."""
    field: str
    years: int


# -- per-subject checks -------------------------------------------------------------------------
@dataclass(frozen=True)
class ExistsCheck:
    """At least one related record exists."""


@dataclass(frozen=True)
class CountCheck:
    """COUNT the related records (optionally inside a time window) and COMPARE."""
    comparison: Comparison
    window: Window | None = None


@dataclass(frozen=True)
class Normalization:
    enabled: bool = False
    remove: tuple[str, ...] = ()
    case_insensitive: bool = False


@dataclass(frozen=True)
class AtLeastCheck:
    """A related record's `field` is at least `minimum`. With `ordering` (the configuration's values, lowest
    first) values compare by their position in it; without one, only equality with `minimum` is decidable.
    `aliases` (alias, ordering value) give other written forms of an ordering value; `normalization` says which
    differences (removed tokens, letter case) do not count when a value is looked up. Both come from the
    configuration; without them a value must equal an ordering value exactly."""
    field: str
    minimum: Any
    ordering: tuple[str, ...] | None = None
    aliases: tuple[tuple[str, str], ...] = ()
    normalization: Normalization = Normalization()


@dataclass(frozen=True)
class Via:
    """The record a subject references: `collection` records whose `key` equals the subject's `subject_field`."""
    subject_field: str
    collection: str
    key: str


@dataclass(frozen=True)
class ShowCheck:
    """A piece of information the configuration requires. Without a `condition` it states no criterion, so it is
    shown to the reviewer and never decides anything: the check always answers `review`. With one it decides:
    operator EXISTS (a value is present) or a comparison operator with the configured value."""
    name: str
    source_field: str | None      # a field of the related records; None = the configuration names no data source
    via: Via | None = None        # set when the field belongs to a record the subject references instead
    condition: Comparison | None = None


Check = ExistsCheck | CountCheck | AtLeastCheck | ShowCheck


# -- measures -----------------------------------------------------------------------------------
@dataclass(frozen=True)
class CountMeasure:
    field: str
    distinct: bool
    comparison: Comparison


@dataclass(frozen=True)
class FormulaMeasure:
    expression: str
    field: str          # record field the expression reads
    reference: str      # name of the reference value the expression reads
    comparison: Comparison


@dataclass(frozen=True)
class FieldsPresentMeasure:
    paths: tuple[str, ...]


@dataclass(frozen=True)
class SubjectMeasure:
    """FILTER subjects, GROUP them by the join keys, JOIN related records, run every check per subject;
    the requirement holds when every subject satisfies every check."""
    subject: Selection
    lookup: Lookup
    checks: tuple[Check, ...]
    manual: tuple[str, ...] | None = None    # set when nothing decides automatically: the statuses a reviewer may choose


@dataclass(frozen=True)
class ReviewMeasure:
    by_user: bool | None
    allowed: tuple[str, ...] = ()            # statuses a manual review may choose from
    # what the reviewer is shown: records of one collection, or a join whose checks only show information
    evidence: Selection | SubjectMeasure | None = None


Measure = CountMeasure | FormulaMeasure | FieldsPresentMeasure | ReviewMeasure | SubjectMeasure


@dataclass(frozen=True)
class GenericExecutionRequest:
    target: str | None
    filters: dict[str, Any]
    measure: Measure
    statuses: dict[str, str]                         # the configuration's `result` map
    prose: list[str] = field(default_factory=list)   # descriptive text, displayed only
    na_enabled: bool = False

    def describe(self) -> str:
        where = "" if not self.filters else " where " + " and ".join(f"{k} = {v!r}" for k, v in self.filters.items())
        m = self.measure
        if isinstance(m, CountMeasure):
            return (f"{'distinct ' if m.distinct else ''}count of {m.field} in {self.target}{where}; "
                    f"compare {m.comparison.operator} {m.comparison.value}")
        if isinstance(m, FormulaMeasure):
            return f"{m.expression} over {self.target}{where}; compare {m.comparison.operator} {m.comparison.value}"
        if isinstance(m, FieldsPresentMeasure):
            return f"fields present in {self.target}{where}: {', '.join(m.paths)}"
        if isinstance(m, SubjectMeasure):
            return _describe_subjects(m)
        if isinstance(m, ReviewMeasure) and isinstance(m.evidence, SubjectMeasure):
            return f"review required by configuration; shown to the reviewer: {_describe_subjects(m.evidence)}"
        return "review required by configuration"


def _selection(s: Selection) -> str:
    parts = [f"{k} = {v!r}" for k, v in s.equals.items()] + [f"{k} in {list(v)!r}" for k, v in s.any_of.items()]
    return s.collection + (" where " + " and ".join(parts) if parts else "")


def _describe_subjects(m: SubjectMeasure) -> str:
    keys = ", ".join(f"{a} = {m.lookup.collection}.{b}" for a, b in m.lookup.pairs)
    checks = "; ".join(type(c).__name__ for c in m.checks)
    return (f"for each distinct ({', '.join(a for a, _ in m.lookup.pairs)}) of {_selection(m.subject)}: "
            f"join {_selection(Selection(m.lookup.collection, m.lookup.equals, m.lookup.any_of))} on {keys}; "
            f"checks: {checks}")
