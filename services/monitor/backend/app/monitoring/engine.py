"""Generic monitoring engine.

interpret (ConfigurationInterpreter) -> GenericExecutionRequest -> execute with generic
capabilities against source data read through the repository. The engine never looks at
the PS code, never names a business field, and reads no database directly.
"""
import logging
from typing import Any

from app.error_log import EVALUATION_ERROR
from app.models.schemas import DataGroup, Issue, PSResult, SummaryItem, Verification
from app.models.source_schema import CURRICULUM_LINK, DISPLAY_FIELD, REFERENCES, SOURCE_SCHEMA
from app.models.status import Status
from app.monitoring import capabilities as cap
from app.monitoring.context import EvaluationContext, name_of
from app.monitoring import subject_checks as checks
from app.monitoring.helpers import ConfigError, SpecGap, describe_config, display, get_path, is_blank
from app.monitoring.interpreter import ConfigurationInterpreter
from app.monitoring.outcome import Outcome
from app.repositories.base import DataSourceError
from app.monitoring.request import (
    CountCheck, CountMeasure, FieldsPresentMeasure, FormulaMeasure, GenericExecutionRequest, ReviewMeasure, ShowCheck,
    SubjectMeasure,
)

# Line prefixes under Missing Information, and the issue each one reports (first match wins).
_ERROR = "Configuration error: "
_FAILED = "Evaluation error: "
_GAP = "SPEC GAP: "
_ISSUES: tuple[tuple[str, Issue], ...] = ((_ERROR, "configuration_error"), (_FAILED, "evaluation_error"),
                                          (_GAP, "spec_gap"))
_log = logging.getLogger(__name__)


class MonitoringEngine:
    def __init__(self, interpreter: ConfigurationInterpreter | None = None) -> None:
        self._interpreter = interpreter or ConfigurationInterpreter()

    def evaluate(self, ps_doc: dict[str, Any], ctx: EvaluationContext) -> PSResult:
        ctx.reset_trace()
        cfg = ps_doc.get("config")
        outcome = self._outcome(cfg, ctx, str(ps_doc.get("psCode", "")))
        review = cfg.get("review") if isinstance(cfg, dict) and isinstance(cfg.get("review"), dict) else {}
        flag = lambda v: v if isinstance(v, bool) else None      # noqa: E731  (shown only when it is a flag)
        requirement = ps_doc.get("requirement")
        return PSResult(
            ps_code=str(ps_doc.get("psCode", "")),
            status=outcome.status,
            requirement=None if requirement is None else str(requirement),
            checks=describe_config(cfg) if isinstance(cfg, dict) else [],
            data_summary=outcome.summary,
            data_found=outcome.found,
            verification=Verification(found=ctx.found_count),
            missing_information=outcome.missing,
            evidence=[],  # evidence source is a SPEC GAP
            traceability=ctx.trace_items(),
            data_completeness="incomplete" if outcome.missing else "complete",
            issue=self._issue(outcome.missing),
            review_required=flag(review.get("required")),
            review_by_user=flag(review.get("reviewByUser")),
        )

    @staticmethod
    def _issue(missing: list[str]) -> Issue | None:
        """A configuration error, else a SPEC GAP, else none: what must be fixed first comes first."""
        for prefix, issue in _ISSUES:
            if any(line.startswith(prefix) for line in missing):
                return issue
        return None

    def _outcome(self, cfg: Any, ctx: EvaluationContext, key: str) -> Outcome:
        try:
            plan = self._interpreter.interpret(cfg)
            if plan.errors or plan.gaps or plan.request is None:
                return Outcome(self._review_status(cfg),
                               missing=[f"{_ERROR}{e}" for e in plan.errors] + [f"{_GAP}{g}" for g in plan.gaps])
            return self._execute(plan.request, ctx, key)
        except SpecGap as gap:
            return Outcome(self._review_status(cfg), missing=[f"{_GAP}{gap}"])
        except ConfigError as err:
            return Outcome(self._review_status(cfg), missing=[f"{_ERROR}{err}"])
        except DataSourceError:
            raise                                   # a source failure is not a result (API: 503)
        except Exception as exc:                    # SRS §48 Evaluation Error: reported for this one result only
            _log.exception("evaluation of %s failed", key, extra={"category": EVALUATION_ERROR})
            return Outcome(self._review_status(cfg), missing=[f"{_FAILED}{type(exc).__name__}: {exc}"])

    @staticmethod
    def _review_status(cfg: Any) -> Status:
        """The status the configuration itself provides for what cannot be decided."""
        for key in ("review", "unknown"):
            try:
                return Status(cfg["result"][key])
            except (KeyError, TypeError, ValueError):
                continue
        return Status.REVIEW  # configuration too incomplete to say; reported with a configuration error

    # -- execution ------------------------------------------------------------------------------
    def _execute(self, req: GenericExecutionRequest, ctx: EvaluationContext, key: str) -> Outcome:
        m = req.measure
        summary = [SummaryItem(label="Operation", value=req.describe())]
        if isinstance(m, ReviewMeasure):
            return self._review(req, m, ctx, key, summary)
        if isinstance(m, SubjectMeasure):
            return self._subjects(req, m, ctx, summary, key)
        assert req.target is not None
        if isinstance(m, CountMeasure):
            return self._count(req, m, ctx, summary)
        if isinstance(m, FormulaMeasure):
            return self._formula(req, m, ctx, summary)
        assert isinstance(m, FieldsPresentMeasure)
        return self._fields_present(req, m, ctx, summary)

    def _review(self, req, m: ReviewMeasure, ctx, key: str, summary) -> Outcome:
        found, missing = [], []
        if isinstance(m.evidence, SubjectMeasure):
            # what the reviewer is shown, subject by subject; its checks only show information and decide nothing
            shown = self._subjects(req, m.evidence, ctx, summary, key)
            found, missing = shown.found, shown.missing
        elif m.evidence is not None:
            records = cap.select_records(ctx, m.evidence.collection, dict(m.evidence.equals), (), any_of=m.evidence.any_of)
            found = [DataGroup(label=m.evidence.collection, items=self._named_records(ctx, m.evidence.collection, records))]
        note = SummaryItem(label="Review", value="Review by user required by configuration" if m.by_user
                           else "Review required by configuration")      # a note, not missing data
        chosen = ctx.manual.get(key)
        if chosen is None:
            return Outcome(self._undecided(req), summary + [note], found, missing)
        if chosen not in m.allowed:
            return Outcome(self._undecided(req), summary + [note], found,
                           missing + [f"{_GAP}manual result '{chosen}' is not among the configured allowManualResult"])
        summary.append(SummaryItem(label="Manual result", value=chosen))
        return Outcome(Status(chosen), summary, found, missing)

    @staticmethod
    def _status(req: GenericExecutionRequest, key: str) -> Status:
        try:
            return Status(req.statuses[key])
        except (KeyError, ValueError):
            raise ConfigError(f"result.{key} is missing or is not a status") from None

    def _undecided(self, req: GenericExecutionRequest) -> Status:
        """The configured status for what cannot be decided: `result.review`, else `result.unknown` (the same order as
        `_review_status`). Only a configuration that names neither is a configuration error; missing data never is."""
        try:
            return self._status(req, "review")
        except ConfigError:
            return self._status(req, "unknown")

    def _gap(self, req: GenericExecutionRequest, reasons: list[str], summary, found=None, missing=None) -> Outcome:
        return Outcome(self._undecided(req), summary, found or [], (missing or []) + [f"{_GAP}{r}" for r in reasons])

    def _count(self, req, m: CountMeasure, ctx, summary) -> Outcome:
        if m.distinct:
            cap.require_scalar(req.target, m.field)
        records = cap.select_records(ctx, req.target, req.filters, (m.field,))
        count, unusable, _ = cap.count_values(records, m.field, m.distinct)
        summary += [SummaryItem(label=f"{'Distinct ' if m.distinct else ''}{m.field} count", value=str(count)),
                    SummaryItem(label="Condition", value=f"{m.comparison.operator} {m.comparison.value}")]
        values = [v for v in (get_path(r, m.field) for r in records) if not is_blank(v)]
        names = ctx.names(m.field, values)
        found = [DataGroup(label=m.field, items=sorted({name_of(names, v) for v in values}))]
        if unusable:
            return self._gap(req, [f"{unusable} record(s) lack {m.field}; reviewCondition is prose and does not define "
                                   "how such records affect the count"], summary, found)
        ok = cap.compare(m.comparison.operator, count, m.comparison.value)
        return Outcome(self._status(req, "pass" if ok else "fail"), summary, found)

    def _formula(self, req, m: FormulaMeasure, ctx, summary) -> Outcome:
        records = cap.select_records(ctx, req.target, req.filters, (m.field,))
        if not records:
            return self._gap(req, [f"no {req.target} records were found; the configuration does not define this case"], summary)
        verdicts: list[Status] = []
        found, missing = [], []
        shown = self._named_records(ctx, req.target, records)
        for rec, rid in zip(records, shown):
            value = get_path(rec, m.field)
            if not isinstance(value, int) or isinstance(value, bool):
                missing.append(f"{rid}: {m.field} is missing or not an integer")
                verdicts.append(self._undecided(req))
                continue
            summary.append(SummaryItem(label=m.field, value=str(value)))
            try:
                reference = ctx.references.resolve(m.reference)
            except SpecGap as gap:
                return self._gap(req, [str(gap)], summary, found, missing)
            result = cap.evaluate_formula(m.expression, {m.field: value, m.reference: reference})
            ok = cap.compare(m.comparison.operator, result, m.comparison.value)
            verdicts.append(self._status(req, "pass" if ok else "fail"))
            found.append(DataGroup(label=rid, items=[f"{m.reference} = {reference}", f"{m.expression} = {result}"]))
        return self._uniform(req, verdicts, summary, found, missing)

    def _fields_present(self, req, m: FieldsPresentMeasure, ctx, summary) -> Outcome:
        """Every selected record must have every configured field; anything absent is the configured `fail`."""
        records = cap.select_records(ctx, req.target, req.filters, m.paths)
        if not records:
            summary.append(SummaryItem(label="Records checked", value="0"))
            return Outcome(self._status(req, "fail"), summary, [], [f"no {req.target} records were found"])
        items, missing, incomplete = [], [], 0
        for rec, rid in zip(records, self._named_records(ctx, req.target, records, with_id=True)):
            gaps = cap.missing_fields(rec, m.paths)
            incomplete += bool(gaps)
            items.append(f"{rid}: " + (f"missing {', '.join(gaps)}" if gaps else "complete"))
            missing += [f"{rid}: {g}" for g in gaps]
        summary += [SummaryItem(label="Records checked", value=str(len(records))),
                    SummaryItem(label="Records with missing fields", value=str(incomplete))]
        found = [DataGroup(label="Records", items=items)]
        return Outcome(self._status(req, "fail" if incomplete else "pass"), summary, found, missing)

    def _subjects(self, req, m: SubjectMeasure, ctx, summary, key: str) -> Outcome:
        """FILTER subjects, GROUP by the join keys, JOIN related records, run each check per subject."""
        keys = tuple(a for a, _ in m.lookup.pairs)
        env = checks.CheckEnv()
        if any(isinstance(c, CountCheck) and c.window for c in m.checks):
            env.anchor = ctx.references.period_anchor()
            env.in_anchor_calendar = ctx.references.in_anchor_calendar
        records = cap.select_records(ctx, m.subject.collection, dict(m.subject.equals), keys, any_of=m.subject.any_of)
        groups, unusable = cap.group_by(records, keys)
        summary.append(SummaryItem(label="Subjects", value=str(len(groups))))
        notes = [f"{len(unusable)} {m.subject.collection} record(s) lack {', '.join(keys)}"] if unusable else []
        if not groups:
            return self._no_subjects(req, m, summary, notes)
        fields =tuple(f for c in m.checks for f in checks.fields_read(c))
        related = cap.find_related(ctx, m.lookup, list(groups), fields)
        referenced = self._referenced(ctx, m, keys, list(groups))
        verdicts, found, gaps, missing = [], [], [], list(notes)
        label = self._subject_labels(ctx, m.subject.collection, keys, list(groups))
        for group in groups:
            results = [checks.run(c, referenced[n](group) if n in referenced else related[group], env)
                       for n, c in enumerate(m.checks)]
            statuses = [self._undecided(req) if r.label == "review" else self._status(req, r.label) for r in results]
            verdicts.append(self._combine(statuses))
            found.append(DataGroup(label=label(group),
                                   items=[f"{r.detail} -> {s.value}" for r, s in zip(results, statuses)]))
            gaps += [g for r in results for g in r.gaps]
            missing += [x for r in results for x in r.missing]
        if unusable:
            verdicts.append(self._undecided(req))
        summary += [SummaryItem(label=f"Subjects {s.value}", value=str(verdicts.count(s))) for s in Status if s in verdicts]
        overall = self._combine(verdicts)
        if m.manual is not None:                      # nothing decides automatically: the reviewer does
            overall, extra = self._manual(req, m.manual, ctx.manual.get(key), overall, summary)
            missing += extra
        return Outcome(overall, summary, found, list(dict.fromkeys(missing)) + [f"{_GAP}{g}" for g in dict.fromkeys(gaps)])

    def _manual(self, req, allowed: tuple[str, ...], chosen: str | None, overall: Status, summary) -> tuple[Status, list[str]]:
        """The reviewer's choice replaces the result. Until there is one, a note (not missing data) says so."""
        if chosen is None:
            summary.append(SummaryItem(label="Review", value="Manual review required: the configuration states no "
                                                             "criterion to decide these items automatically"))
            return overall, []
        if chosen not in allowed:
            return self._undecided(req), [f"{_GAP}manual result '{chosen}' is not among the statuses the configuration names"]
        summary.append(SummaryItem(label="Manual result", value=chosen))
        return Status(chosen), []

    def _no_subjects(self, req, m: SubjectMeasure, summary, notes: list[str]) -> Outcome:
        """No subject exists. With naEnabled and a configured `na` status the requirement does not apply."""
        if req.na_enabled and not notes:
            summary.append(SummaryItem(label="Not applicable", value=f"no {m.subject.collection} record is selected"))
            return Outcome(self._status(req, "na"), summary)
        return Outcome(self._undecided(req), summary,
                       missing=notes + [f"no {m.subject.collection} record is selected, so nothing can be checked"])

    @staticmethod
    def _referenced(ctx, m: SubjectMeasure, keys: tuple[str, ...], groups: list[tuple]) -> dict:
        """For each check (by position) that reads a record the subjects reference: subject -> those records."""
        out = {}
        for n, c in enumerate(m.checks):
            if isinstance(c, ShowCheck) and c.via is not None:
                if c.via.subject_field not in keys:
                    raise SpecGap(f"'{c.via.subject_field}' is not a key of the subjects, so {c.via.collection} "
                                  "records cannot be read for them")
                i = keys.index(c.via.subject_field)
                recs = cap.find_referenced(ctx, c.via.collection, c.via.key, [g[i] for g in groups], (c.source_field,))
                out[n] = lambda group, recs=recs, i=i: recs.get(group[i], [])
        return out

    # -- display only: names instead of ids; never part of a result ------------------------------------
    @staticmethod
    def _subject_labels(ctx, collection: str, keys: tuple[str, ...], groups: list[tuple]):
        """Label each subject by its key values, shown by name. The key that scopes the subjects to the
        monitored curriculum has the same value for every subject, so it is left out of the label."""
        shown = [i for i, k in enumerate(keys) if k != CURRICULUM_LINK.get(collection)] or list(range(len(keys)))
        names = {i: ctx.names(keys[i], [g[i] for g in groups]) for i in shown}
        return lambda group: ", ".join(name_of(names[i], group[i]) for i in shown)

    @staticmethod
    def _named_records(ctx, collection: str, records: list, with_id: bool = False) -> list[str]:
        """Each record shown by its own name field (DISPLAY_FIELD), if its collection has one, and by the names
        of the records it references (except the curriculum scope key). A record with neither is shown by its
        id; `with_id` keeps the id after the name, for records that several may share a name with."""
        own = DISPLAY_FIELD.get(collection)
        fields = [f for f in SOURCE_SCHEMA.get(collection, {}) if f in REFERENCES and f != CURRICULUM_LINK.get(collection)]
        names = {f: ctx.names(f, [get_path(r, f) for r in records]) for f in fields}
        shown = []
        for rec in records:
            rid = str(rec.get("_id", "?"))
            parts = [display(get_path(rec, own))] if own and not is_blank(get_path(rec, own)) else []
            parts += [name_of(names[f], get_path(rec, f)) for f in fields if not is_blank(get_path(rec, f))]
            text = ", ".join(parts)
            shown.append(rid if not text else f"{text} ({rid})" if with_id else text)
        return shown

    @staticmethod
    def _combine(statuses: list[Status]) -> Status:
        """Any fail fails; otherwise anything undecided is a review; only all-pass passes."""
        if Status.FAIL in statuses:
            return Status.FAIL
        return Status.PASS if statuses and all(s is Status.PASS for s in statuses) else Status.REVIEW

    def _uniform(self, req, verdicts: list[Status], summary, found, missing) -> Outcome:
        """Only the unambiguous combination is decided: every record has the same status."""
        if len(set(verdicts)) == 1:
            return Outcome(verdicts[0], summary, found, missing)
        return self._gap(req, ["results differ between records and the specification does not define how they combine"],
                         summary, found, missing)
