"""Interpretation of subject-based operations.

A configuration that joins two collections, or matches records of one collection against each
other, describes: which records are the subjects, which related records they are joined to, and
what each subject must satisfy. This module recognises that from the *structure* of the
configuration and from the Data Schema; it holds no PS code and no business word:

* `<prefix><Field>: value(s)`      -> FILTER on the declared field named by the last word of the key
* `<collection>: {field: value}`  -> FILTER on that collection (its name, singular, is the key)
* `join`                          -> JOIN pairs of `collection.field` references
* `matching: {same<X>: true}`     -> JOIN on the declared field `<x>Id` of the same collection
* `{field, period}`               -> TIME WINDOW over a year field (whole numbers; the reference source puts
                                     each year in the anchor's calendar)
* `minimumCount`                  -> COUNT of related records compared with >=
* `{field, minimum}`              -> at-least comparison of a related field (equality with the minimum only)
* `{field, minimum, ordering}`    -> at-least comparison by position in `ordering` (lowest first); optional
                                     `aliases` {ordering value: [other written forms]} and `normalization`
                                     {enabled, remove, caseInsensitive} say how a value finds its position
* `{source, required}`            -> information for the reviewer to see (no criterion: never decides); the
                                     source is a field of the related records, or of a record the subjects
                                     reference (Data Schema REFERENCES, e.g. a `<x>Id` key)
* `{source, required, condition}` -> the same information, decided by `condition`: {operator: EXISTS} or
                                     {operator, value} with an operator the engine can execute
* `join` with `review`            -> what the reviewer is shown when the user decides (`reviewed_subjects`):
                                     information only, nothing decided automatically

Anything it does not recognise is left for the interpreter to report as a SPEC GAP.
"""
import re
from dataclasses import dataclass, replace
from typing import Any

from app.models.status import Status
from app.models.source_schema import CURRICULUM_LINK, REFERENCES, SOURCE_SCHEMA, declared_type
from app.monitoring.capabilities import SUPPORTED_OPERATORS
from app.monitoring.interpreter_base import Interpretation
from app.monitoring.normalize import normalize
from app.monitoring.request import (
    AtLeastCheck, Check, Comparison, CountCheck, ExistsCheck, Lookup, Normalization, Selection, ShowCheck,
    SubjectMeasure, Via, Window,
)

_WORDS = re.compile(r"[A-Z]?[a-z0-9]+")
_SAME = re.compile(r"^same([A-Z][A-Za-z0-9]*)$")
_PERIOD = re.compile(r"^previous(\d+)Years$")
_REF = re.compile(r"^(?P<collection>[a-z_]+)\.(?P<field>[A-Za-z0-9_.]+)$")


@dataclass
class Filter:
    key: str
    collection: str
    field: str
    values: tuple
    is_list: bool


def named_collections(cfg: dict[str, Any], seen: set[str], out: Interpretation) -> list[str]:
    names: list[str] = []
    for key in ("targetCollection", "targetCollections"):
        if key not in cfg:
            continue
        seen.add(key)
        value = cfg[key]
        for name in ([value] if isinstance(value, str) else value if isinstance(value, list) else []):
            if isinstance(name, str) and name in SOURCE_SCHEMA:
                names.append(name)
            else:
                out.errors.append(f"{key} '{name}' is not a source data collection")
    return names


def field_filters(cfg: dict[str, Any], seen: set[str], collections: list[str]) -> list[Filter]:
    """FILTER constructs: a key whose last word names a field declared by exactly one of `collections`."""
    found: list[Filter] = []
    for key, value in cfg.items():
        if key in seen:
            continue
        is_list = isinstance(value, list)
        values = tuple(value) if is_list else (value,)
        if not values or not all(isinstance(v, str) for v in values):
            continue
        words = _WORDS.findall(key)
        matches = [(c, f) for c in collections for f in _candidates(words[-1].lower() if words else "") if declared_type(c, f)]
        if len(matches) != 1:
            continue
        seen.add(key)
        found.append(Filter(key, matches[0][0], matches[0][1], values, is_list))
    return found


def _candidates(word: str) -> list[str]:
    return [word, word[:-1]] if word.endswith("s") else [word]


def _block_filters(cfg: dict[str, Any], seen: set[str], collections: list[str]) -> list[tuple[str, dict[str, Any]]]:
    """`<collection singular>: {field: value}` -> equality FILTER on that collection."""
    blocks = []
    for key, value in cfg.items():
        if key in seen or not isinstance(value, dict) or not value:
            continue
        owners = [c for c in collections if c.startswith(key)]
        if len(owners) == 1 and all(isinstance(v, (str, int)) and declared_type(owners[0], f) for f, v in value.items()):
            seen.add(key)
            blocks.append((owners[0], dict(value)))
    return blocks


def _split(filters: list[Filter], collection: str, out: Interpretation) -> tuple[dict[str, Any], dict[str, tuple]]:
    equals: dict[str, Any] = {}
    any_of: dict[str, tuple] = {}
    for f in (f for f in filters if f.collection == collection):
        if f.field in equals or f.field in any_of:
            out.gaps.append(f"{f.key}: '{collection}.{f.field}' is filtered twice, and the configuration does not say how the filters combine")
        elif f.is_list:
            any_of[f.field] = f.values
        else:
            equals[f.field] = f.values[0]
    return equals, any_of


def review_evidence(cfg: dict[str, Any], seen: set[str], out: Interpretation) -> Selection | None:
    """The records a reviewer is shown: the target collection filtered by the configuration's filters."""
    named = named_collections(cfg, seen, out)
    if len(named) != 1:
        return None
    equals, any_of = _split(field_filters(cfg, seen, named), named[0], out)
    return Selection(named[0], equals, any_of)


def reviewed_subjects(cfg: dict[str, Any], seen: set[str], out: Interpretation) -> SubjectMeasure | None:
    """What the reviewer is shown when a `join` comes with a user review: each subject and the information the
    configuration requires, read from the joined records. The user decides, so a check that decides (a condition,
    a count, an ordering) is a SPEC GAP: it would take the decision away from the reviewer."""
    measure = interpret_subjects(cfg, seen, out)
    if measure is None:
        return None
    if not all(isinstance(c, ShowCheck) and c.condition is None for c in measure.checks):
        out.gaps.append("a join reviewed by the user may only show information (no condition, count or ordering): "
                        "the reviewer decides, so nothing may be decided automatically")
        return None
    return replace(measure, manual=None)


# -- subject-based operation ----------------------------------------------------------------------
def interpret_subjects(cfg: dict[str, Any], seen: set[str], out: Interpretation) -> SubjectMeasure | None:
    named = named_collections(cfg, seen, out)
    return _self_lookup(cfg, seen, out, named) if "matching" in cfg else _joined(cfg, seen, out, named)


def _self_lookup(cfg, seen, out, named) -> SubjectMeasure | None:
    seen.update({"matching", "condition"})
    if len(named) != 1:
        out.gaps.append("matching needs exactly one targetCollection")
        return None
    collection = named[0]
    pairs: list[tuple[str, str]] = []
    matching = cfg["matching"] if isinstance(cfg["matching"], dict) else {}
    for key, value in matching.items():
        m = _SAME.match(key)
        field = (m.group(1)[0].lower() + m.group(1)[1:] + "Id") if m else None
        if field and value is True and declared_type(collection, field):
            pairs.append((field, field))
        else:
            out.gaps.append(f"no technical definition for: matching.{key}")
    condition = cfg.get("condition")
    if not (isinstance(condition, dict) and condition.get("operator") == "EXISTS" and isinstance(condition.get("field"), str)):
        out.errors.append("matching needs condition {operator: EXISTS, field}")
        return None
    unknown = [k for k in condition if k not in ("operator", "field")]
    if unknown:
        out.gaps.append("no technical definition for: " + ", ".join(f"condition.{k}" for k in unknown))
    filters = field_filters(cfg, seen, named)
    related = [f for f in filters if f.values == (condition["field"],)]
    subject = [f for f in filters if f not in related]
    if len(related) != 1 or len(subject) != 1 or related[0].field != subject[0].field or not pairs:
        out.gaps.append("EXISTS needs one filter selecting the subjects, one selecting the related records "
                        "(the value named by condition.field), and at least one same<X> key")
        return None
    s_eq, s_any = _split(subject, collection, out)
    l_eq, l_any = _split(related, collection, out)
    return SubjectMeasure(Selection(collection, s_eq, s_any), Lookup(collection, tuple(pairs), l_eq, l_any), (ExistsCheck(),))


def _ref(value: Any) -> tuple[str, str] | None:
    m = _REF.match(value) if isinstance(value, str) else None
    return (m["collection"], m["field"]) if m and declared_type(m["collection"], m["field"]) else None


def _joined(cfg, seen, out, named) -> SubjectMeasure | None:
    seen.add("join")
    join = cfg.get("join")
    refs = {k: _ref(v) for k, v in join.items()} if isinstance(join, dict) else {}
    bad = [k for k, r in refs.items() if r is None]
    if not refs or bad:
        out.gaps.append("join is not a set of 'collection.field' references declared by the Data Schema"
                        + (": " + ", ".join(f"join.{k}" for k in bad) if bad else ""))
        return None
    if set(refs) == {"from", "to"}:
        (subject_c, subject_f), (lookup_c, lookup_f) = refs["from"], refs["to"]
        pairs = [(subject_f, lookup_f)]
    else:
        collections = sorted({c for c, _ in refs.values()})
        linked = [c for c in collections if c in CURRICULUM_LINK]
        if len(linked) != 1 or len(collections) != len(linked) + 1:
            out.gaps.append("join does not identify which of its two collections holds the subjects "
                            "(the one linked to the curriculum)")
            return None
        subject_c, lookup_c = linked[0], next(c for c in collections if c != linked[0])
        subject_fields = {f for c, f in refs.values() if c == subject_c}
        lookup_fields = {f for c, f in refs.values() if c == lookup_c}
        pairs = [(f, f) for f in sorted(subject_fields & lookup_fields)]
        stray = [k for k, (c, f) in refs.items() if (c == subject_c and f not in lookup_fields and f != CURRICULUM_LINK[subject_c])
                 or (c == lookup_c and f not in subject_fields)]
        if stray:
            out.gaps.append("no technical definition for: " + ", ".join(f"join.{k}" for k in stray))
    if subject_c not in CURRICULUM_LINK or not pairs:
        out.gaps.append("join gives no way to scope the subjects to the monitored curriculum or no key to join on")
        return None
    outside = [c for c in named if c not in (subject_c, lookup_c)]
    if outside:
        out.gaps.append(f"targetCollection(s) {', '.join(outside)} take no part in the join")
    collections = [subject_c, lookup_c]
    filters = field_filters(cfg, seen, collections)
    s_eq, s_any = _split(filters, subject_c, out)
    l_eq, l_any = _split(filters, lookup_c, out)
    for collection, equals in _block_filters(cfg, seen, collections):
        (s_eq if collection == subject_c else l_eq).update(equals)
    checks = _checks(cfg, seen, out, lookup_c, tuple(a for a, _ in pairs))
    if not checks:
        out.gaps.append("the configuration states nothing for each subject to satisfy")
        return None
    manual = _manual_choices(cfg) if all(isinstance(c, ShowCheck) and c.condition is None for c in checks) else None
    return SubjectMeasure(Selection(subject_c, s_eq, s_any), Lookup(lookup_c, tuple(pairs), l_eq, l_any), tuple(checks), manual)


# -- checks --------------------------------------------------------------------------------------
def _checks(cfg, seen, out, lookup: str, subject_keys: tuple[str, ...] = ()) -> list[Check]:
    checks: list[Check] = []
    minimum = cfg.get("minimumCount")
    window: Window | None = None
    if "minimumCount" in cfg:
        seen.add("minimumCount")
    for key, value in list(cfg.items()):
        if key in seen or not isinstance(value, dict):
            continue
        keys = set(value)
        if keys == {"field", "period"}:
            seen.add(key)
            window = _window(key, value, lookup, out)
        elif {"field", "minimum"} <= keys <= {"field", "minimum", "ordering", "aliases", "normalization"} \
                and ("ordering" in keys or not keys & {"aliases", "normalization"}):
            seen.add(key)
            ranked = _ranked(key, value, out) if "ordering" in keys else None
            if not declared_type(lookup, str(value["field"])):
                out.gaps.append(f"{key}.field '{value['field']}' is not declared for '{lookup}' by the Data Schema")
            elif "ordering" not in keys:
                checks.append(AtLeastCheck(value["field"], value["minimum"]))
            elif ranked is not None:
                checks.append(ranked)
        elif "required" in keys and keys <= {"required", "source", "condition"}:
            seen.add(key)
            _information(key, value, lookup, subject_keys, checks, out)
    if isinstance(minimum, int) and not isinstance(minimum, bool):
        checks.append(CountCheck(Comparison(">=", minimum), window))
    elif window is not None or "minimumCount" in cfg:
        out.errors.append("minimumCount must be an integer, and a time window needs it")
    return checks


def _ordering(key: str, block: dict[str, Any], out: Interpretation) -> tuple[str, ...] | None:
    """`ordering`: the configuration's values, lowest first; the minimum must be one of them."""
    ordering = block["ordering"]
    if not isinstance(ordering, list) or not ordering or not all(isinstance(v, str) for v in ordering) \
            or len(set(ordering)) != len(ordering):
        out.errors.append(f"{key}.ordering must be a list of distinct text values, lowest first")
        return None
    if block["minimum"] not in ordering:
        out.errors.append(f"{key}.minimum is not one of {key}.ordering")
        return None
    return tuple(ordering)


def _ranked(key: str, block: dict[str, Any], out: Interpretation) -> AtLeastCheck | None:
    """`{field, minimum, ordering}` with the optional `aliases` and `normalization` that say how a value finds its
    position. After normalization every written form (ordering value or alias) must name exactly one ordering value."""
    ordering = _ordering(key, block, out)
    normalization = _normalization(block.get("normalization"), out)
    aliases = block.get("aliases", {})
    if ordering is None or normalization is None:
        return None
    if not isinstance(aliases, dict) or not all(
            isinstance(forms, list) and all(isinstance(f, str) for f in forms) for forms in aliases.values()):
        out.errors.append(f"{key}.aliases must map {key}.ordering values to lists of text values")
        return None
    unknown = [str(k) for k in aliases if k not in ordering]
    if unknown:
        out.errors.append(f"{key}.aliases names value(s) that are not in {key}.ordering: {', '.join(unknown)}")
        return None
    pairs = tuple((form, value) for value, forms in aliases.items() for form in forms)
    names: dict[str, str] = {}
    for form, value in [(v, v) for v in ordering] + list(pairs):
        written = normalize(form, normalization)
        if not written:
            out.errors.append(f"{key}: '{form}' is empty after {key}.normalization")
            return None
        if names.setdefault(written, value) != value:
            out.errors.append(f"{key}: '{form}' names more than one {key}.ordering value after {key}.normalization")
            return None
    return AtLeastCheck(block["field"], block["minimum"], ordering, pairs, normalization)


def _window(key: str, block: dict[str, Any], lookup: str, out: Interpretation) -> Window | None:
    period = _PERIOD.match(block["period"]) if isinstance(block["period"], str) else None
    if not period:
        out.gaps.append(f"no technical definition for: {key}.period '{block['period']}'")
        return None
    if not declared_type(lookup, str(block["field"])):
        out.gaps.append(f"{key}.field '{block['field']}' is not declared for '{lookup}' by the Data Schema")
        return None
    return Window(block["field"], int(period.group(1)))


def _information(name: str, block: dict[str, Any], lookup: str, subject_keys: tuple[str, ...], checks: list[Check],
                 out: Interpretation) -> None:
    """Required information with a source (or none): shown to the reviewer, and judged only by a configured condition."""
    if not isinstance(block["required"], bool):
        out.errors.append(f"{name}.required must be true or false")
    elif block["required"]:
        condition = _condition(name, block["condition"], out) if "condition" in block else None
        if "condition" in block and condition is None:
            return
        source = block.get("source")
        ref = _ref(source)
        via = _via(ref[0], subject_keys) if ref else None
        if source is None:
            checks.append(ShowCheck(name, None))
        elif ref and ref[0] == lookup:
            checks.append(ShowCheck(name, ref[1], condition=condition))
        elif ref and via:
            checks.append(ShowCheck(name, ref[1], via, condition))
        else:
            out.gaps.append(f"{name}.source is not a field of '{lookup}', nor of a record the subjects reference, "
                            "declared by the Data Schema")


def _condition(name: str, block: Any, out: Interpretation) -> Comparison | None:
    """`{operator: EXISTS}`, or `{operator, value}` with an executable operator and a single value."""
    if isinstance(block, dict) and block.get("operator") == "EXISTS" and set(block) == {"operator"}:
        return Comparison("EXISTS", None)
    if isinstance(block, dict) and set(block) == {"operator", "value"} and block["operator"] in SUPPORTED_OPERATORS \
            and isinstance(block["value"], (bool, int, float, str)):
        return Comparison(block["operator"], block["value"])
    out.errors.append(f"{name}.condition must be {{operator: EXISTS}} or {{operator, value}} with an operator "
                      "the engine can execute and a single value")
    return None


def _via(collection: str, subject_keys: tuple[str, ...]) -> Via | None:
    """The subject key that references a record of `collection` (Data Schema REFERENCES), if exactly one does."""
    found = [Via(k, *REFERENCES[k]) for k in subject_keys if REFERENCES.get(k, ("",))[0] == collection]
    return found[0] if len(found) == 1 else None


def _manual_choices(cfg: dict[str, Any]) -> tuple[str, ...]:
    """Statuses the configuration's `conditions` name, except N/A (which means nothing was selected)."""
    conditions = cfg.get("conditions")
    valid = {s.value for s in Status if s is not Status.NA}
    values = conditions.values() if isinstance(conditions, dict) else []
    return tuple(dict.fromkeys(v for v in values if isinstance(v, str) and v in valid))


def _normalization(block: Any, out: Interpretation) -> Normalization | None:
    if block is None:
        return Normalization()
    if not isinstance(block, dict) or not isinstance(block.get("remove", []), list):
        out.errors.append("normalization must be an object with a list 'remove'")
        return None
    unknown = [f"normalization.{k}" for k in block if k not in ("enabled", "remove", "caseInsensitive")]
    if unknown:
        out.gaps.append("no technical definition for: " + ", ".join(unknown))
    return Normalization(block.get("enabled") is True, tuple(str(t) for t in block.get("remove", [])),
                         block.get("caseInsensitive") is True)
