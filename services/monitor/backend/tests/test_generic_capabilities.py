"""Generic capabilities, tested without naming any PS.

Two kinds of test: the capabilities directly (filter, group, join, compare, window, normalize,
reference) and configurations whose *shape* differs from every authoritative PS, proving the
interpreter reads structure and the Data Schema, not the PS it happens to know.
"""
from datetime import date

import pytest

from app.models.status import Status
from app.monitoring import capabilities as cap
from app.monitoring import subject_checks as sc
from app.monitoring.context import EvaluationContext
from app.monitoring.helpers import SpecGap
from app.monitoring.normalize import normalize
from app.monitoring.reference import UndefinedReferences
from app.monitoring.request import (
    AtLeastCheck, Comparison, CountCheck, ExistsCheck, Lookup, Normalization, ShowCheck, Via, Window,
)
from app.references.runtime import RuntimeReferences
from app.repositories.source_data import SourceDataRepository
from app.settings import Settings
from tests.support.fixtures import base_data, make_service, oid, results
from tests.support.memory_store import InMemorySourceAdapter

PASS, FAIL, REVIEW, NA = Status.PASS, Status.FAIL, Status.REVIEW, Status.NA


def context(data):
    return EvaluationContext(data["curricula"][0], SourceDataRepository(InMemorySourceAdapter(data)), UndefinedReferences())


def run_one(data, config, requirement="x", **kw):
    """Execute one ad-hoc configuration; nothing about it is a known PS."""
    data["ps_requirements"] = [{"psCode": "any", "requirement": requirement, "active": True, "config": config}]
    return results(data, **kw)["any"]


RESULT = {"pass": "PASS", "fail": "FAIL", "review": "REVIEW", "na": "N/A"}


# =============================== FILTER / GROUP / JOIN ===============================
def test_filter_by_equality_and_by_membership(data):
    ctx = context(data)
    roles = {a["role"] for a in cap.select_records(ctx, "appointments", {}, ())}
    assert roles == {"programmeResponsible", "programmeStaff"}
    one = cap.select_records(ctx, "appointments", {}, (), any_of={"role": ["programmeStaff"]})
    assert {a["role"] for a in one} == {"programmeStaff"}
    none = cap.select_records(ctx, "appointments", {"role": "programmeStaff"}, (), any_of={"role": ["programmeResponsible"]})
    assert none == []                                           # both conditions apply


def test_group_by_one_and_several_keys_and_records_lacking_a_key(data):
    recs = [{"a": 1, "b": 1}, {"a": 1, "b": 2}, {"a": 2, "b": 1}, {"a": None, "b": 1}, {"b": 1}, {"a": "", "b": 1}]
    groups, unusable = cap.group_by(recs, ("a",))
    assert {k: len(v) for k, v in groups.items()} == {(1,): 2, (2,): 1} and len(unusable) == 3
    groups, _ = cap.group_by(recs[:3], ("a", "b"))
    assert set(groups) == {(1, 1), (1, 2), (2, 1)}


def test_join_reads_the_lookup_collection_once_and_matches_in_memory(data):
    ctx = context(data)
    source = ctx.source._adapter
    people = [a["personId"] for a in data["appointments"] if a["role"] == "programmeResponsible"]
    related = cap.find_related(ctx, Lookup("educations", (("personId", "personId"),)), [(p,) for p in people], ("degree",))
    assert source.calls.count(("find", "educations")) == 1                 # one read for all subjects
    assert all(len(v) == 1 for v in related.values()) and set(related) == {(p,) for p in people}


def test_join_on_several_pairs_needs_every_pair_to_match(data):
    ctx = context(data)
    cid = data["curricula"][0]["_id"]
    p = data["appointments"][0]["personId"]
    lookup = Lookup("appointments", (("curriculumId", "curriculumId"), ("personId", "personId")), {"role": "programmeStaff"})
    hit = cap.find_related(ctx, lookup, [(cid, p), (oid(), p), (cid, oid())], ())
    assert [len(v) for v in hit.values()] == [1, 0, 0]


def test_join_with_a_undeclared_field_is_a_spec_gap(data):
    with pytest.raises(SpecGap):
        cap.find_related(context(data), Lookup("educations", (("personId", "nope"),)), [(oid(),)], ())


# =============================== COMPARISON / COUNT / WINDOW ===============================
@pytest.mark.parametrize("op,left,right,expected", [
    ("==", 1, 1, True), ("!=", 1, 1, False), (">", 2, 1, True), (">=", 1, 1, True), ("<", 1, 1, False), ("<=", 1, 1, True)])
def test_every_comparison_operator(op, left, right, expected):
    assert cap.compare(op, left, right) is expected


def test_unknown_comparison_operator_is_a_spec_gap():
    with pytest.raises(SpecGap):
        cap.compare("~=", 1, 1)


def works(*years):
    return [{"publicationYear": y} for y in years]


@pytest.mark.parametrize("years,window,minimum,expected", [
    ((2564, 2569), 5, 2, "pass"),           # both ends of the window are inside
    ((2563, 2569), 5, 2, "fail"),           # one year too old
    ((2570,), 5, 1, "fail"),                # a year after the reference is outside
    ((2569,), 0, 1, "pass"),                # a zero-year window is the reference year alone
    ((), 5, 1, "fail")])
def test_time_window_is_reference_minus_years_through_reference(years, window, minimum, expected):
    check = CountCheck(Comparison(">=", minimum), Window("publicationYear", window))
    assert sc.run(check, works(*years), sc.CheckEnv(anchor=2569)).label == expected


def test_count_without_a_window_counts_every_related_record():
    assert sc.run(CountCheck(Comparison(">=", 2)), works(1, 2), sc.CheckEnv()).label == "pass"
    assert sc.run(CountCheck(Comparison("==", 3)), works(1, 2), sc.CheckEnv()).label == "fail"


def test_unusable_years_only_matter_when_they_could_change_the_answer():
    env = sc.CheckEnv(anchor=2569)
    check = CountCheck(Comparison(">=", 1), Window("publicationYear", 5))
    assert sc.run(check, works(2569, None), env).label == "pass"           # already enough
    assert sc.run(check, works(None, "x", True), env).label == "review"    # cannot tell
    assert sc.run(CountCheck(Comparison("<=", 0), Window("publicationYear", 5)), works(None), env).label == "review"


def test_at_least_only_decides_what_equality_decides():
    check = AtLeastCheck("degree", "b")
    assert sc.run(check, [{"degree": "a"}, {"degree": "b"}], sc.CheckEnv()).label == "pass"
    other = sc.run(check, [{"degree": "c"}], sc.CheckEnv())
    assert other.label == "review" and "no ordering" in other.gaps[0]
    assert sc.run(check, [{"degree": ""}, {}], sc.CheckEnv()).label == "review"
    assert sc.run(check, [], sc.CheckEnv()).label == "review"


def test_at_least_by_a_configured_ordering_compares_positions():
    check = AtLeastCheck("level", "b", ("a", "b", "c"))                    # generic values: the ordering is data
    run = lambda *values: sc.run(check, [{"level": v} for v in values], sc.CheckEnv())   # noqa: E731
    assert run("a").label == "fail" and run("b").label == "pass" and run("c").label == "pass"
    assert run("a", "c").label == "pass"                                    # the highest counts
    assert run("x").label == "review" and "not in the configured ordering: x" in run("x").missing[0]
    assert run("a", "x").label == "review" and run("c", "x").label == "pass"  # an unlisted value blocks a fail only
    assert run().label == "review" and run("", None).label == "review"
    assert run(["b"], {"b": 1}).label == "review"                           # non-scalar values have no position


def test_required_information_with_a_condition_decides():
    exists = ShowCheck("x", "v", condition=Comparison("EXISTS", None))
    equals = ShowCheck("x", "v", condition=Comparison("==", True))
    run = lambda check, *records: sc.run(check, list(records), sc.CheckEnv())   # noqa: E731
    assert run(exists, {"v": "a"}).label == "pass" and run(exists, {"v": "a"}, {"v": ""}).label == "pass"
    assert run(exists).label == "fail"                                      # no joined record: there is none
    assert run(exists, {"v": ""}, {}).label == "review"                     # a record without the value
    assert run(equals, {"v": True}).label == "pass" and run(equals, {"v": False}).label == "fail"
    assert run(equals, {"v": 1}).label == "review"                          # 1 is not a Boolean: never taken as true
    assert run(equals, {"v": "true"}).label == "review" and run(equals).label == "review"
    via = Via("k", "c", "_id")
    assert sc.run(ShowCheck("x", "v", via, Comparison("EXISTS", None)), [], sc.CheckEnv()).label == "review"   # missing reference


def test_information_for_review_is_shown_and_never_judged():
    seen = sc.run(ShowCheck("x", "a"), [{"a": "v1"}, {"a": "v2"}, {"a": ""}], sc.CheckEnv())
    assert seen.label == "review" and seen.detail == "x: v1, v2" and seen.gaps == [] and seen.missing == []
    empty = sc.run(ShowCheck("x", "a"), [{"a": None}], sc.CheckEnv())
    assert empty.label == "review" and empty.missing and empty.gaps == []
    none = sc.run(ShowCheck("x", None), [{"a": 1}], sc.CheckEnv())
    assert none.label == "review" and "no data source" in none.gaps[0]
    assert sc.run(ExistsCheck(), [], sc.CheckEnv()).label == "fail"


# =============================== NORMALIZATION ===============================
def test_normalize_removes_tokens_in_listed_order_and_can_ignore_case():
    n = Normalization(True, ("long token", "token", " ", "-"), True)
    assert normalize("A Long Token-Word TOKEN", n) == "aword"
    assert normalize("A-b", Normalization(False, ("-",), True)) == "A-b"          # disabled: unchanged
    assert normalize("A-b", Normalization(True, ("-",), False)) == "Ab"           # case kept


# =============================== REFERENCES ===============================
def test_runtime_reference_is_the_clock_year_in_the_configured_calendar():
    today = lambda: date(2026, 9, 20)
    assert RuntimeReferences(543, today).resolve("currentYear") == 2569
    assert RuntimeReferences(0, today).resolve("currentYear") == 2026
    assert RuntimeReferences(543, today).period_anchor() == 2569


def test_runtime_reference_does_not_know_other_names():
    with pytest.raises(SpecGap):
        RuntimeReferences(543).resolve("someOtherName")


def test_nothing_defined_means_a_spec_gap():
    with pytest.raises(SpecGap):
        UndefinedReferences().resolve("x")
    with pytest.raises(SpecGap):
        UndefinedReferences().period_anchor()


def test_the_calendar_is_a_setting_not_a_constant_of_evaluation(monkeypatch):
    assert Settings.from_env().year_offset == 543
    monkeypatch.setenv("MORNITOR_YEAR_OFFSET", "0")
    assert Settings.from_env().year_offset == 0


def test_production_wiring_uses_the_runtime_resolver():
    from app.api.dependencies import get_service
    get_service.cache_clear()
    assert isinstance(get_service()._references, RuntimeReferences)
    get_service.cache_clear()


# =============================== configurations shaped unlike any authoritative PS ===============================
def usage_data(n=3, degree="x"):
    data = base_data()
    cid = data["curricula"][0]["_id"]
    for _ in range(n):
        edu = {"_id": oid(), "personId": oid(), "degree": degree, "field": "f"}
        data["educations"].append(edu)
        data["data_usages"] = data.get("data_usages", []) + [
            {"_id": oid(), "dataType": "education", "dataId": edu["_id"], "curriculumId": cid}]
    return data


JOIN_ON_ID = {"targetCollection": "data_usages", "join": {"from": "data_usages.dataId", "to": "educations._id"},
              "data_usage": {"dataType": "education"}, "level": {"field": "degree", "minimum": "x"}, "result": RESULT}


def test_a_join_between_other_collections_on_other_fields_executes(data):
    data = usage_data()
    r = run_one(data, JOIN_ON_ID)
    assert r.status is PASS and next(i.value for i in r.data_summary if i.label == "Subjects") == "3"
    assert {t.collection for t in r.traceability} == {"data_usages", "educations"}


def test_that_join_reacts_to_data_and_configuration(data):
    data = usage_data(degree="y")
    assert run_one(data, JOIN_ON_ID).status is REVIEW                        # 'y' is not comparable with 'x'
    assert run_one(data, {**JOIN_ON_ID, "level": {"field": "degree", "minimum": "y"}}).status is PASS
    assert run_one(data, {**JOIN_ON_ID, "data_usage": {"dataType": "other"}}).status is REVIEW   # no subjects, naEnabled absent


def test_the_undecided_status_is_result_review_else_result_unknown(data):
    """Nothing to check is the configured undecided status; only a result map naming neither is a configuration error."""
    none_selected = {**JOIN_ON_ID, "data_usage": {"dataType": "other"}}
    with_unknown = {"pass": "PASS", "fail": "FAIL", "unknown": "REVIEW"}
    r = run_one(usage_data(), {**none_selected, "result": with_unknown})
    assert r.status is REVIEW and r.issue is None
    r = run_one(usage_data(), {**none_selected, "result": {**with_unknown, "unknown": "FAIL"}})
    assert r.status is FAIL and r.issue is None                             # the configuration's own choice
    r = run_one(usage_data(), {**none_selected, "result": {"pass": "PASS", "fail": "FAIL"}})
    assert r.status is REVIEW and r.issue == "configuration_error"


def test_multiple_conditions_are_all_required(data):
    data = usage_data()
    both = {**JOIN_ON_ID, "minimumCount": 1}                                 # at-least AND a count per subject
    assert run_one(data, both).status is PASS
    assert run_one(data, {**both, "minimumCount": 2}).status is FAIL         # one condition fails -> the requirement fails
    assert run_one(data, {**both, "level": {"field": "degree", "minimum": "y"}, "minimumCount": 2}).status is FAIL   # fail beats review


def test_information_without_a_criterion_is_never_decided_by_the_engine(data):
    data = usage_data()
    info = {**{k: v for k, v in JOIN_ON_ID.items() if k != "level"}, "info": {"required": True, "source": "educations.field"}}
    r = run_one(data, info)
    assert r.status is REVIEW and any("info: f" in i for i in (i for g in r.data_found for i in g.items))
    assert run_one(data, {**info, "conditions": {"a": "PASS", "b": "FAIL"}}).status is REVIEW      # still not decided
    data2 = {**data, "educations": []}
    assert run_one(data2, info).status is REVIEW


def test_na_needs_naEnabled_and_the_configured_status(data):
    data = usage_data(0)
    assert run_one(data, JOIN_ON_ID).status is REVIEW
    assert run_one(data, {**JOIN_ON_ID, "naEnabled": True}).status is NA
    assert "result.na" in " ".join(run_one(data, {**JOIN_ON_ID, "naEnabled": True, "result": {"review": "REVIEW"}}).missing_information)


@pytest.mark.parametrize("mutate,expected", [
    (lambda c: c["join"].update(extra="educations.nope"), "join"),                      # reference not in the Data Schema
    (lambda c: c.update(data_usage={"dataType": "education", "nope": 1}), "data_usage"),  # filter on an undeclared field
    (lambda c: c.update(level={"field": "nope", "minimum": "x"}), "not declared"),
    (lambda c: c.update(unknownKey=True), "unknownKey"),
    (lambda c: c.update(join={"from": "data_usages.dataId"}), "join"),
])
def test_what_the_schema_or_the_interpreter_does_not_define_is_a_spec_gap(data, mutate, expected):
    config = {**JOIN_ON_ID, "join": dict(JOIN_ON_ID["join"])}
    mutate(config)
    r = run_one(usage_data(), config)
    assert r.status is REVIEW and expected in " ".join(r.missing_information) and "SPEC GAP" in " ".join(r.missing_information)
    assert r.traceability == []                                                        # nothing was read


def test_the_psCode_plays_no_part(data):
    data = usage_data()
    data["ps_requirements"] = [{"psCode": "anything", "active": True, "config": JOIN_ON_ID}]
    assert results(data)["anything"].status is PASS


def test_a_whole_run_of_the_authoritative_configuration_only_reads(data):
    service, source = make_service(data)
    service.monitor()
    assert {op for op, _ in source.calls} == {"find"}
