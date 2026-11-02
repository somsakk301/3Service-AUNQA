"""Generation readiness: may the external document generator use the PS results of this curriculum?

Everything that decides it comes from one document of the configuration collection, told apart by its
configType (project owner, 2026-09-26). Nothing about which PS are required or which statuses allow
or block is assumed here. A document that is missing, duplicated or malformed gives no decision: it
is reported as an issue, never replaced by a default.

The only rule defined is the one for requiredAll true (project owner, 2026-09-26):
* READY: every required PS has an active PS configuration and a result, and every result is an allowedStatus.
* NOT_READY: a required PS has a blockedStatus result, or has no active PS configuration
  (configuration problem) or no result (data problem).
Whatever the owner has not defined is not decided here: it is reported for a decision.
"""
from dataclasses import dataclass

from app.models.schemas import BlockingPS, GenerationReadiness, Issue, PSResult
from app.models.status import Readiness, Status
from app.repositories.base import Document
from app.repositories.configuration import CONFIG_TYPE_KEY

CONFIG_TYPE = "generationReadiness"   # the configType value, and the key that holds the configuration
_STATUSES = [s.value for s in Status]


class ReadinessConfigProblem(Exception):
    """The configuration document cannot decide readiness."""

    def __init__(self, issue: Issue, detail: str) -> None:
        super().__init__(detail)
        self.issue = issue
        self.detail = detail


@dataclass(frozen=True)
class ReadinessRule:
    required: tuple[str, ...]
    allowed: frozenset[str]
    blocked: frozenset[str]


def _error(detail: str) -> ReadinessConfigProblem:
    return ReadinessConfigProblem("configuration_error", detail)


def _statuses(when: dict, key: str) -> set[str]:
    values = when.get(key)
    if not isinstance(values, list) or not values:
        raise _error(f"readyWhen.{key} is missing, empty or not an array")
    unknown = [v for v in values if v not in _STATUSES]
    if unknown:
        raise _error(f"readyWhen.{key} names unknown status(es) {unknown}; known: {_STATUSES}")
    return set(values)


def validate(doc: Document) -> ReadinessRule:
    """The rule the document states. Keys the specification does not name are not read."""
    if CONFIG_TYPE_KEY not in doc:
        raise _error(f"{CONFIG_TYPE_KEY} is missing")
    if doc[CONFIG_TYPE_KEY] != CONFIG_TYPE:
        raise _error(f"{CONFIG_TYPE_KEY} is {doc[CONFIG_TYPE_KEY]!r}, not {CONFIG_TYPE!r}")
    body = doc.get(CONFIG_TYPE)
    if not isinstance(body, dict):
        raise _error(f"{CONFIG_TYPE} is missing or not an object")

    required = body.get("requiredPS")
    if not isinstance(required, list):
        raise _error("requiredPS is missing or not an array")
    if not required:
        raise _error("requiredPS is empty")
    if not all(isinstance(c, str) and c.strip() for c in required):
        raise _error("requiredPS must list PS codes as text")

    when = body.get("readyWhen")
    if not isinstance(when, dict):
        raise _error("readyWhen is missing or not an object")
    allowed, blocked = _statuses(when, "allowedStatus"), _statuses(when, "blockedStatus")
    if both := [s for s in _STATUSES if s in allowed & blocked]:
        raise _error(f"status(es) {both} are both allowedStatus and blockedStatus")

    every = body.get("requiredAll")
    if not isinstance(every, bool):
        raise _error("requiredAll is missing or not a boolean")
    if not every:
        raise ReadinessConfigProblem(
            "spec_gap", "requiredAll is false: no rule is defined for it, so nothing is decided (decision needed)")
    return ReadinessRule(tuple(required), frozenset(allowed), frozenset(blocked))


def _undecided(issue: Issue, detail: str) -> GenerationReadiness:
    return GenerationReadiness(status=None, issue=issue, detail=detail)


def _code(doc: Document) -> str:
    return str(doc.get("psCode", ""))   # the name the engine gives the result of this configuration


def decide(docs: list[Document], requirements: list[Document], results: list[PSResult]) -> GenerationReadiness:
    """`docs`: every stored document of this configType; `requirements`: the active PS configurations."""
    if not docs:
        return _undecided("configuration_error",
                          f"no configuration document with {CONFIG_TYPE_KEY} {CONFIG_TYPE!r} was found")
    if len(docs) > 1:
        return _undecided("configuration_error",
                          f"{len(docs)} configuration documents with {CONFIG_TYPE_KEY} {CONFIG_TYPE!r}; exactly one is expected")
    try:
        rule = validate(docs[0])
    except ReadinessConfigProblem as problem:
        return _undecided(problem.issue, problem.detail)

    active = set(map(_code, requirements))
    statuses: dict[str, list[Status]] = {}
    for result in results:   # the status readiness counts: a saved user review where there is one (2026-09-27)
        statuses.setdefault(result.ps_code, []).append(result.readiness_status())
    blocking, unconfigured, unevaluated, unclassified = [], [], [], []
    for code in dict.fromkeys(rule.required):
        found = statuses.get(code, [])
        if code not in active or not found:
            (unconfigured if code not in active else unevaluated).append(code)
            blocking.append(BlockingPS(ps_code=code, status=None))
        elif hit := next((s for s in found if s.value in rule.blocked), None):
            blocking.append(BlockingPS(ps_code=code, status=hit))
        elif any(s.value not in rule.allowed for s in found):
            unclassified.append(code)

    if blocking:
        details = []
        if unconfigured:
            details.append(f"requiredPS {unconfigured} have no active PS configuration")
        if unevaluated:
            details.append(f"requiredPS {unevaluated} have no evaluation result")
        return GenerationReadiness(status=Readiness.NOT_READY, blocking_ps=blocking,
                                   issue="configuration_error" if unconfigured else None,
                                   detail="; ".join(details) or None)
    if unclassified:
        return _undecided("spec_gap", f"the status of {unclassified} is neither an allowedStatus nor a blockedStatus: "
                                      "no rule is defined for it, so nothing is decided (decision needed)")
    return GenerationReadiness(status=Readiness.READY)
