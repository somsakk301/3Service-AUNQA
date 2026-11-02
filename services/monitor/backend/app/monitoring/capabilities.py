"""Generic technical capabilities: FILTER, COUNT, DISTINCT, COMPARE, FIELD_PRESENT, formula.

None of them knows what a value means; they only operate on what the configuration names.
"""
import operator
import re
from typing import Any, Mapping, Sequence

from app.models.source_schema import CURRICULUM_KEY, CURRICULUM_LINK, declared_type, is_container
from app.monitoring.context import EvaluationContext
from app.monitoring.helpers import ConfigError, SpecGap, get_path, is_blank, is_hashable
from app.repositories.base import Document
from app.monitoring.request import Lookup
from app.repositories.source_data import SourceQuery

_OPERATORS = {">=": operator.ge, ">": operator.gt, "<=": operator.le, "<": operator.lt, "==": operator.eq, "!=": operator.ne}
SUPPORTED_OPERATORS = tuple(_OPERATORS)
_TOKEN = re.compile(r"\s*(?:([A-Za-z_][A-Za-z0-9_]*)|(\d+)|([+-]))")


def compare(op: str, left: Any, right: Any) -> bool:
    if op not in _OPERATORS:
        raise SpecGap(f"comparison operator '{op}' is not supported by the engine")
    try:
        return _OPERATORS[op](left, right)
    except TypeError:
        raise ConfigError(f"cannot compare {left!r} {op} {right!r}") from None


def select_records(ctx: EvaluationContext, target: str, filters: dict[str, Any], fields: tuple[str, ...],
                   any_of: Mapping[str, Sequence[Any]] | None = None) -> list[Document]:
    """FILTER the monitored curriculum's records of `target`, using the Data Dictionary relationship."""
    link = CURRICULUM_LINK.get(target)
    if link is None:
        raise SpecGap(f"the Data Dictionary declares no relationship between '{target}' and curricula, "
                      "so its records cannot be scoped to the monitored curriculum")
    any_of = any_of or {}
    paths = (*fields, *filters.keys(), *any_of.keys())
    check_declared(target, paths)
    return ctx.find(target, SourceQuery(equals={link: ctx.curriculum.get(CURRICULUM_KEY), **filters},
                                        any_of={k: tuple(v) for k, v in any_of.items()}), paths)


def group_by(records: list[Document], keys: tuple[str, ...]) -> tuple[dict[tuple, list[Document]], list[Document]]:
    """GROUP records by the values of `keys`. Returns (groups, records lacking a key value)."""
    groups: dict[tuple, list[Document]] = {}
    unusable: list[Document] = []
    for rec in records:
        key = tuple(get_path(rec, k) for k in keys)
        if any(is_blank(v) or not is_hashable(v) for v in key):
            unusable.append(rec)
        else:
            groups.setdefault(key, []).append(rec)
    return groups, unusable


def find_related(ctx: EvaluationContext, lookup: Lookup, keys: list[tuple], fields: tuple[str, ...]) -> dict[tuple, list[Document]]:
    """JOIN: the `lookup` records whose join fields equal each subject key. Read once, matched in memory."""
    join_fields = tuple(b for _, b in lookup.pairs)
    paths = (*join_fields, *lookup.equals, *lookup.any_of, *fields)
    check_declared(lookup.collection, paths)
    wanted = {f: tuple(sorted({k[i] for k in keys}, key=str)) for i, f in enumerate(join_fields)}
    query = SourceQuery(equals=dict(lookup.equals), any_of={**{k: tuple(v) for k, v in lookup.any_of.items()}, **wanted})
    related: dict[tuple, list[Document]] = {k: [] for k in keys}
    for rec in ctx.find(lookup.collection, query, paths):
        key = tuple(get_path(rec, f) for f in join_fields)
        if key in related:
            related[key].append(rec)
    return related


def find_referenced(ctx: EvaluationContext, collection: str, key: str, values: list, fields: tuple[str, ...]) -> dict:
    """The `collection` records whose `key` equals each value (a Data Schema reference). Read once, traced."""
    paths = (key, *fields)
    check_declared(collection, paths)
    wanted = tuple(sorted(set(values), key=str))
    found: dict = {v: [] for v in wanted}
    for rec in ctx.find(collection, SourceQuery(any_of={key: wanted}), paths):
        k = get_path(rec, key)
        if k in found:
            found[k].append(rec)
    return found


def check_declared(target: str, paths: tuple[str, ...]) -> None:
    """Every field the configuration names must be declared by the Data Schema; none is assumed or approximated."""
    undeclared = sorted({p for p in paths if declared_type(target, p) is None})
    if undeclared:
        raise SpecGap(f"the Data Schema declares no field {', '.join(undeclared)} in '{target}', so it is not read or compared")
    for path in paths:
        parts = path.split(".")
        if any((declared_type(target, ".".join(parts[:i])) or "").startswith("Array") for i in range(1, len(parts))):
            raise SpecGap(f"'{target}.{path}' lies inside an array; the engine defines no way to read it")


def require_scalar(target: str, field: str) -> None:
    """A declared Object/Array field has no defined distinct value, so counting it is not defined."""
    declared = declared_type(target, field)
    if declared is not None and is_container(declared):
        raise SpecGap(f"'{target}.{field}' is declared as {declared}; counting its values is not defined")


def count_values(records: list[Document], field: str, distinct: bool) -> tuple[int, int, list[str]]:
    """COUNT / DISTINCT of `field`. Returns (count, records lacking the field, values seen)."""
    values = [get_path(r, field) for r in records]
    usable = [v for v in values if not is_blank(v) and (is_hashable(v) or not distinct)]
    count = len(set(usable)) if distinct else len(records)
    return count, len(values) - len(usable), sorted({str(v) for v in usable})


def missing_fields(record: Document, paths: tuple[str, ...]) -> list[str]:
    """FIELD_PRESENT: the configured paths that are absent or empty in `record`."""
    return [p for p in paths if is_blank(get_path(record, p))]


def formula_identifiers(expression: str) -> list[str]:
    return [t[0] for t in _tokens(expression) if t[0]]


def _tokens(expression: str) -> list[tuple[str, str, str]]:
    out, pos = [], 0
    while pos < len(expression):
        m = _TOKEN.match(expression, pos)
        if not m:
            if expression[pos:].strip():
                raise SpecGap(f"formula '{expression}' is not supported (only names, integers, + and -)")
            break
        out.append(m.groups())
        pos = m.end()
    return out


def evaluate_formula(expression: str, bindings: dict[str, int]) -> int:
    total, sign, expect_operand = 0, 1, True
    for name, number, op in _tokens(expression):
        if op:
            if expect_operand:
                raise SpecGap(f"formula '{expression}' is not supported")
            sign, expect_operand = (1 if op == "+" else -1), True
            continue
        if not expect_operand:
            raise SpecGap(f"formula '{expression}' is not supported")
        if name and name not in bindings:
            raise SpecGap(f"formula name '{name}' is not bound by the configuration")
        total += sign * (bindings[name] if name else int(number))
        expect_operand = False
    if expect_operand:
        raise SpecGap(f"formula '{expression}' is not supported")
    return total
