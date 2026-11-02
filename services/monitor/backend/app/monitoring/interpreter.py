"""Configuration Interpreter.

Reads one `ps_requirements.config` and either returns a GenericExecutionRequest or lists,
precisely, the parts it cannot execute. It recognises only technical constructs (what to
read, filter, count, compare, require, calculate, flag for review). It holds no business
vocabulary of any kind, and it selects nothing by PS code.

Anything else in the configuration is reported as a SPEC GAP, never guessed and never
silently ignored:
  * a key whose meaning the interpreter has no technical definition for
  * no construct, or more than one, that says which operation is wanted
  * an operator, formula or name the generic capabilities cannot execute

Subject-based operations (join / matching between records) are interpreted by `subject_interpreter`.
"""
import re
from typing import Any

from app.monitoring.capabilities import SUPPORTED_OPERATORS, formula_identifiers
from app.models.source_schema import declared_type
from app.models.status import Status
from app.monitoring.helpers import SpecGap
from app.monitoring.interpreter_base import Interpretation
from app.monitoring.request import (
    Comparison, CountMeasure, FieldsPresentMeasure, FormulaMeasure, GenericExecutionRequest, ReviewMeasure, SubjectMeasure,
)
from app.monitoring.subject_interpreter import interpret_subjects, review_evidence, reviewed_subjects
from app.repositories.source_data import SOURCE_COLLECTIONS

PROSE_KEYS = ("reviewCondition", "conditions")  # descriptive text, displayed only
_FLAG = re.compile(r"[A-Za-z0-9]+Required")


class ConfigurationInterpreter:
    def interpret(self, cfg: Any) -> Interpretation:
        out = Interpretation()
        if not isinstance(cfg, dict):
            out.errors.append("missing 'config'")
            return out
        seen: set[str] = {"result", "naEnabled", *PROSE_KEYS}
        statuses = cfg.get("result")
        if not isinstance(statuses, dict):
            out.errors.append("missing 'result'")

        wanted = self._operation(cfg)
        planned = wanted in ("review", "join", "matching")     # these read their own collections
        target = None if planned else self._target(cfg, seen, out)
        filters = {} if planned else self._filters(cfg, seen, out)
        measure = self._measure(cfg, seen, out, wanted)
        if cfg.get("naEnabled") is True and not isinstance(measure, SubjectMeasure):
            out.gaps.append("naEnabled is true, but this operation defines no not-applicable condition")
        self._unaccounted(cfg, seen, out)
        if not (out.gaps or out.errors) and measure is not None:
            out.request = GenericExecutionRequest(
                target=target, filters=filters, measure=measure, statuses=dict(statuses),
                prose=[f"{k}: {cfg[k]}" for k in PROSE_KEYS if k in cfg], na_enabled=cfg.get("naEnabled") is True)
        return out

    @staticmethod
    def _operation(cfg: dict[str, Any]) -> str | None:
        present = [k for k in ("count", "calculation", "requiredFields", "review", "join", "matching") if k in cfg]
        # `join` and `matching` both describe one subject-based operation
        if len(present) == 1 or set(present) == {"join", "matching"}:
            return present[0]
        # a review whose `join` says what the reviewer is shown: the review is the operation
        return "review" if set(present) == {"review", "join"} else None

    # -- constructs -------------------------------------------------------------------------
    def _target(self, cfg: dict[str, Any], seen: set[str], out: Interpretation) -> str | None:
        if "targetCollection" not in cfg:
            return None
        seen.add("targetCollection")
        target = cfg["targetCollection"]
        if not isinstance(target, str) or target not in SOURCE_COLLECTIONS:
            out.errors.append(f"targetCollection '{target}' is not a source data collection")
            return None
        return target

    def _filters(self, cfg: dict[str, Any], seen: set[str], out: Interpretation) -> dict[str, Any]:
        if "filter" not in cfg:
            return {}
        seen.add("filter")
        flt = cfg["filter"]
        if not isinstance(flt, dict) or any(isinstance(v, (dict, list)) for v in flt.values()):
            out.gaps.append("filter is not a set of single-value equality conditions")
            return {}
        return dict(flt)

    def _measure(self, cfg: dict[str, Any], seen: set[str], out: Interpretation, wanted: str | None):
        if wanted is None:
            present = [k for k in ("count", "calculation", "requiredFields", "review", "join", "matching") if k in cfg]
            out.gaps.append("the configuration does not identify exactly one operation "
                            f"(constructs present: {', '.join(present) or 'none'})")
            return None
        if wanted in ("join", "matching"):
            return interpret_subjects(cfg, seen, out)
        return getattr(self, f"_{wanted}")(cfg, seen, out)

    def _count(self, cfg, seen, out):
        seen.update({"count", "condition"})
        count, cond = cfg["count"], cfg.get("condition")
        self._keys(count, "count", {"field", "distinct"}, out)
        comparison = self._comparison(cond, "condition", out, ("operator", "value"))
        if not isinstance(count, dict) or not isinstance(count.get("field"), str) or not isinstance(count.get("distinct"), bool):
            out.errors.append("count needs 'field' (text) and 'distinct' (true/false)")
            return None
        if cfg.get("targetCollection") is None:
            out.errors.append("missing 'targetCollection'")
        return CountMeasure(count["field"], count["distinct"], comparison) if comparison else None

    def _calculation(self, cfg, seen, out):
        seen.update({"calculation", "comparison", "year"})
        calc, year = cfg["calculation"], cfg.get("year")
        self._keys(calc, "calculation", {"formula"}, out)
        self._keys(year, "year", {"field"}, out)
        comparison = self._comparison(cfg.get("comparison"), "comparison", out, ("operator", "value", "reference"))
        formula = calc.get("formula") if isinstance(calc, dict) else None
        field_name = year.get("field") if isinstance(year, dict) else None
        reference = cfg.get("comparison", {}).get("reference") if isinstance(cfg.get("comparison"), dict) else None
        if not all(isinstance(x, str) for x in (formula, field_name, reference)):
            out.errors.append("calculation needs 'calculation.formula', 'year.field' and 'comparison.reference' (text)")
            return None
        try:
            unbound = [n for n in formula_identifiers(formula) if n not in (field_name, reference)]
        except SpecGap as gap:
            out.gaps.append(str(gap))
            return None
        if unbound:
            out.gaps.append(f"formula name(s) not bound by the configuration: {', '.join(unbound)}")
            return None
        if cfg.get("targetCollection") is None:
            out.errors.append("missing 'targetCollection'")
        return FormulaMeasure(formula, field_name, reference, comparison) if comparison else None

    def _requiredFields(self, cfg, seen, out):
        seen.add("requiredFields")
        fields = cfg["requiredFields"]
        if not isinstance(fields, list) or not all(isinstance(f, str) for f in fields):
            out.errors.append("requiredFields must be a list of field names")
            return None
        paths: list[str] = []
        for name in fields:
            paths.append(name)
            nested = cfg.get(name)
            if nested is None:
                continue
            seen.add(name)                       # an object named after a required field describes that field
            if not isinstance(nested, dict):
                out.gaps.append(f"{name}: not an object describing the required field")
                continue
            flags = [k for k in nested if isinstance(k, str) and _FLAG.fullmatch(k)]
            self._keys(nested, name, {"required", "requiredFields", *flags}, out)
            if "required" in nested and nested["required"] is not True:
                out.gaps.append(f"{name}.required other than true has no defined meaning")
            for flag in flags:                   # `<field>Required: true` makes that declared field required too
                wanted = flag[:-len("Required")]
                collection = cfg.get("targetCollection")
                path = next((p for p in (f"{name}.{wanted}", wanted) if declared_type(collection, p)), None)
                if nested[flag] is not True:
                    out.gaps.append(f"{name}.{flag} other than true has no defined meaning")
                elif path is None:
                    out.gaps.append(f"{name}.{flag}: '{wanted}' is not a field of '{collection}' declared by the Data Schema")
                else:
                    paths.append(path)
            subs = nested.get("requiredFields", [])
            if not isinstance(subs, list) or not all(isinstance(s, str) for s in subs):
                out.errors.append(f"{name}.requiredFields must be a list of field names")
                continue
            paths += [f"{name}.{s}" for s in subs]
        if cfg.get("targetCollection") is None:
            out.errors.append("missing 'targetCollection'")
        return FieldsPresentMeasure(tuple(dict.fromkeys(paths)))

    def _review(self, cfg, seen, out):
        seen.add("review")
        review = cfg["review"]
        self._keys(review, "review", {"required", "reviewByUser", "allowManualResult"}, out)
        if not isinstance(review, dict) or review.get("required") is not True:
            out.gaps.append("review without required: true has no defined meaning")
            return None
        allowed = review.get("allowManualResult", [])
        valid = {s.value for s in Status}
        if not isinstance(allowed, list) or not all(a in valid for a in allowed):
            out.gaps.append("review.allowManualResult is not a list of statuses")
            return None
        by_user = review.get("reviewByUser")
        shown = reviewed_subjects(cfg, seen, out) if "join" in cfg else review_evidence(cfg, seen, out)
        return ReviewMeasure(by_user if isinstance(by_user, bool) else None, tuple(allowed), shown)

    # -- helpers ----------------------------------------------------------------------------
    def _comparison(self, block, name, out, keys) -> Comparison | None:
        self._keys(block, name, set(keys), out)
        if not isinstance(block, dict) or "operator" not in block or "value" not in block:
            out.errors.append(f"{name} needs 'operator' and 'value'")
            return None
        if not isinstance(block["operator"], str) or block["operator"] not in SUPPORTED_OPERATORS:
            out.gaps.append(f"{name}.operator '{block['operator']}' is not an operator the engine can execute")
            return None
        if not isinstance(block["value"], (int, float)) or isinstance(block["value"], bool):
            out.errors.append(f"{name}.value must be a number")
            return None
        return Comparison(block["operator"], block["value"])

    @staticmethod
    def _keys(block: Any, name: str, allowed: set[str], out: Interpretation) -> None:
        if isinstance(block, dict):
            unknown = [f"{name}.{k}" for k in block if k not in allowed]
            if unknown:
                out.gaps.append("no technical definition for: " + ", ".join(unknown))

    @staticmethod
    def _unaccounted(cfg: dict[str, Any], seen: set[str], out: Interpretation) -> None:
        unknown = [k for k in cfg if k not in seen]
        if unknown:
            out.gaps.append("no technical definition for: " + ", ".join(unknown))
