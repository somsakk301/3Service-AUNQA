"""Per-subject checks. Each returns a label (a key of the configuration's `result` map) plus what it saw.

A check never decides anything the configuration does not say: when it cannot decide it answers
with the configuration's review label and names the missing definition.
"""
from dataclasses import dataclass, field
from typing import Callable

from app.monitoring import capabilities as cap
from app.monitoring.helpers import display, get_path, is_blank, whole_number
from app.monitoring.normalize import normalize
from app.monitoring.request import AtLeastCheck, Check, CountCheck, ExistsCheck, ShowCheck
from app.repositories.base import Document

_MONOTONE = (">=", ">")   # adding records can only keep such a comparison true


def _unchanged(year: int) -> int:
    return year


@dataclass
class CheckEnv:
    """Values resolved once per evaluation, shared by every subject."""
    anchor: int | None = None
    in_anchor_calendar: Callable[[int], int] = _unchanged   # a stored year, in the calendar of `anchor`


@dataclass
class CheckResult:
    label: str
    detail: str
    gaps: list[str] = field(default_factory=list)      # SPEC GAP: what the specification does not define
    missing: list[str] = field(default_factory=list)   # data the check needed and did not find


def fields_read(check: Check) -> tuple[str, ...]:
    """Fields of the related records a check reads (for traceability and schema validation)."""
    if isinstance(check, CountCheck):
        return (check.window.field,) if check.window else ()
    if isinstance(check, AtLeastCheck):
        return (check.field,)
    if isinstance(check, ShowCheck):
        return (check.source_field,) if check.source_field and check.via is None else ()
    return ()


def run(check: Check, related: list[Document], env: CheckEnv) -> CheckResult:
    if isinstance(check, ExistsCheck):
        return CheckResult("pass" if related else "fail", f"{len(related)} matching record(s)")
    if isinstance(check, CountCheck):
        return _count(check, related, env)
    if isinstance(check, AtLeastCheck):
        return _at_least(check, related)
    assert isinstance(check, ShowCheck)
    return _show(check, related)


def _count(check: CountCheck, related: list[Document], env: CheckEnv) -> CheckResult:
    records, unusable = related, 0
    window = check.window
    if window is not None:
        assert env.anchor is not None
        years = [whole_number(get_path(r, window.field)) for r in related]
        # in the anchor's calendar: the reference source converts a year a record wrote in another calendar
        usable = [(r, env.in_anchor_calendar(y)) for r, y in zip(related, years) if y is not None]
        unusable = len(related) - len(usable)
        low, high = env.anchor - window.years, env.anchor
        records = [r for r, y in usable if low <= y <= high]
    count = len(records)
    ok = cap.compare(check.comparison.operator, count, check.comparison.value)
    detail = f"{count} in window" if window else f"{count} record(s)"
    if unusable and not (ok and check.comparison.operator in _MONOTONE):
        return CheckResult("review", f"{detail}; {unusable} without a usable {window.field}",
                           missing=[f"{unusable} record(s) lack a usable {window.field}"])
    return CheckResult("pass" if ok else "fail", detail)


def _at_least(check: AtLeastCheck, related: list[Document]) -> CheckResult:
    values = [v for v in (get_path(r, check.field) for r in related) if not is_blank(v)]
    shown = ", ".join(sorted({str(v) for v in values})) or "—"
    if check.ordering is not None and values:
        return _ranked(check, values)
    if any(v == check.minimum for v in values):
        return CheckResult("pass", f"{check.field}: {shown} (equal to {check.minimum!r})")
    if not values:
        return CheckResult("review", f"{check.field}: none", missing=[f"no usable {check.field} value"])
    return CheckResult("review", f"{check.field}: {shown}", gaps=[
        f"the specification defines no ordering of {check.field} values, so {shown} cannot be compared with "
        f"the minimum {check.minimum!r} (only equality with it is decidable)"])


def _ranked(check: AtLeastCheck, values: list) -> CheckResult:
    """The subject's highest value by the configured ordering (lowest first), compared with the minimum.
    Only values listed in the ordering, or configured as an alias of one, have a position (looked up after the
    configured normalization; nothing is guessed). An unlisted value could be the highest, so it prevents a fail;
    it cannot prevent a pass that a listed value already reaches. The detail names every distinct value read and
    the ordering value it stands for."""
    position = ordering_positions(check)
    rank = lambda v: position.get(normalize(v, check.normalization)) if isinstance(v, str) else None   # noqa: E731
    listed = [rank(v) for v in values if rank(v) is not None]
    unlisted = sorted({str(v) for v in values if rank(v) is None})
    needed = position[normalize(check.minimum, check.normalization)]
    highest = check.ordering[max(listed)] if listed else None
    ranks: dict[str, int | None] = {}
    for v in values:
        ranks.setdefault(str(v), rank(v))
    read = f"{check.field}: " + "; ".join(
        f"{v} → {check.ordering[p]}" if p is not None else f"{v} → not in the ordering" for v, p in sorted(ranks.items()))
    if listed and max(listed) >= needed:
        return CheckResult("pass", f"{read} (highest {highest!r} is at least {check.minimum!r})")
    if unlisted:
        return CheckResult("review", read, missing=[
            f"{check.field} value(s) not in the configured ordering: {', '.join(unlisted)}"])
    return CheckResult("fail", f"{read} (highest {highest!r} is below {check.minimum!r})")


def ordering_positions(check: AtLeastCheck) -> dict[str, int]:
    """Normalized ordering value or alias -> its position in the ordering (the interpreter rejects collisions)."""
    position = {normalize(v, check.normalization): i for i, v in enumerate(check.ordering)}
    for alias, value in check.aliases:
        position[normalize(alias, check.normalization)] = check.ordering.index(value)
    return position


def _decide(check: ShowCheck, related: list[Document]) -> CheckResult:
    """Required information judged by its configured condition.

    EXISTS: a value is present. A joined collection with no record for the subject has none (fail); a record
    without the value, or a referenced record that is missing, cannot be judged (review).
    A comparison: some value of the configured value's kind compares true (pass); every value is of that kind and
    none does (fail); no value, or a value of another kind, cannot be judged (review). Nothing else is inferred.
    """
    op, expected = check.condition.operator, check.condition.value
    values = [v for v in (get_path(r, check.source_field) for r in related) if not is_blank(v)]
    shown = ", ".join(sorted({display(v) for v in values}))
    if not related and op == "EXISTS" and check.via is None:
        return CheckResult("fail", f"{check.name}: no record")
    if not values:
        return CheckResult("review", f"{check.name}: no value found", missing=[f"{check.name}: no value found for review"])
    if op == "EXISTS":
        return CheckResult("pass", f"{check.name}: {shown}")
    kind = lambda v: bool if isinstance(v, bool) else float if isinstance(v, (int, float)) else type(v)   # noqa: E731
    comparable = [v for v in values if kind(v) is kind(expected)]
    if any(cap.compare(op, v, expected) for v in comparable):
        return CheckResult("pass", f"{check.name}: {shown}")
    if len(comparable) == len(values):
        return CheckResult("fail", f"{check.name}: {shown} (not {op} {display(expected)})")
    return CheckResult("review", f"{check.name}: {shown}", missing=[
        f"{check.name}: {shown} cannot be compared with {display(expected)}"])


def _show(check: ShowCheck, related: list[Document]) -> CheckResult:
    """Collect what the source holds so the reviewer can see it. Nothing is judged."""
    if check.source_field is None:
        return CheckResult("review", f"{check.name}: no data source", gaps=[
            f"{check.name}.source is null: the configuration names no data source, and none is assumed"])
    if check.condition is not None:
        return _decide(check, related)
    values = sorted({display(v) for v in (get_path(r, check.source_field) for r in related) if not is_blank(v)})
    if not values:
        return CheckResult("review", f"{check.name}: no value found", missing=[f"{check.name}: no value found for review"])
    return CheckResult("review", f"{check.name}: {', '.join(values)}")
