"""PS-05 degree forms and PS-07 year calendars found in the real data (project owner 2026-09-27).

PS-05: the ACTIVE config gives `degree.aliases` (ปร.ด. -> Ph.D., วท.ม. -> master, วท.บ. / บธ.บ. / วบ.บ. -> bachelor)
and `degree.normalization` (blanks and dots removed, letter case ignored). The engine only looks values up with
them: a value that is neither an ordering value nor a configured alias stays unlisted (never guessed). Only the
subjects the configuration selects (appointments with the configured role) are judged, on all their educations.
PS-07: some records write publicationYear in the Gregorian calendar (2022-2026) next to Buddhist-era years; the
runtime reference source puts each year in the anchor's calendar before the window is applied, and a year written
as text of digits is read as that number. Nothing else is interpreted as a year.
Every case goes Config -> Interpreter -> Generic Engine -> Data -> Result; no person, curriculum or PS is named in
production code.
"""
import copy
from datetime import date
from pathlib import Path

import pytest
from bson import json_util
from fastapi.testclient import TestClient

from app.api.dependencies import get_service
from app.main import create_app
from app.models.source_schema import SOURCE_SCHEMA
from app.models.status import Status
from app.monitoring.helpers import whole_number
from app.monitoring.reference import UndefinedReferences
from app.references.runtime import RuntimeReferences
from tests.support.fixtures import AUTHORITATIVE_CONFIG, add_person, make_service, oid, results

PASS, FAIL, REVIEW = Status.PASS, Status.FAIL, Status.REVIEW
CLOCK_2026 = RuntimeReferences(543, lambda: date(2026, 9, 27))     # current year 2569 (Buddhist era) = 2026


def cfg(data, code):
    return next(d["config"] for d in data["ps_requirements"] if d["psCode"] == code)


def responsible(data):
    return {a["personId"] for a in data["appointments"] if a["role"] == "programmeResponsible"}


def with_degrees(data, *values):
    """Every responsible person holds exactly these degree values (one education record each)."""
    people = responsible(data)
    data["educations"] = [e for e in data["educations"] if e["personId"] not in people] + [
        {"_id": oid(), "personId": p, "degree": v, "field": "Computer Science"} for p in people for v in values]
    return data


def ps05(data):
    return results(data)["PS-05"]


# =============================== PS-05: the owner's cases ===============================
@pytest.mark.parametrize("values,expected", [
    (("ปร.ด.",), PASS),
    (("วท.ม.",), PASS),
    (("Ph.D.",), PASS),
    (("วท.บ.",), FAIL),
    (("บธ.บ.",), FAIL),
    ((), REVIEW),                                                           # no degree at all
    ((None,), REVIEW), (("",), REVIEW),                                     # a record without a usable degree
    (("heuristic approach. Journal of Sensor and Actuator", "at"), REVIEW),   # malformed only: never guessed
    (("at", "วท.ม."), PASS),                                               # malformed + master
    (("heuristic approach. Journal of Sensor and Actuator", "ปร.ด."), PASS),   # malformed + Ph.D.
    (("วท.บ.", "วท.ม.", "ปร.ด."), PASS),                                   # several records, the highest counts
    (("บธ.บ.", "วท.ม."), PASS),
])
def test_ps05_owner_cases(data, values, expected):
    r = ps05(with_degrees(data, *values))
    assert r.status is expected and r.issue is None


@pytest.mark.parametrize("value,expected", [
    ("ปร. ด.", PASS), ("วท. ม.", PASS), (" วท.ม. ", PASS),                 # blanks
    ("PhD.", PASS), ("ph.d.", PASS), ("PHD", PASS), ("Master", PASS),      # dots and letter case
    ("วท.บ", FAIL), ("วท. บ.", FAIL),
])
def test_ps05_written_variants_rank_through_the_configured_normalization(data, value, expected):
    assert ps05(with_degrees(data, value)).status is expected


@pytest.mark.parametrize("values", [("at",), ("วศ.ม.",), ("Technology (International Program)",)])
def test_ps05_a_form_the_configuration_does_not_give_is_never_guessed(data, values):
    r = ps05(with_degrees(data, *values))
    assert r.status is REVIEW and f"not in the configured ordering: {values[0]}" in " ".join(r.missing_information)


def test_ps05_an_unlisted_value_still_prevents_a_fail(data):
    """Kept from before (2026-09-25): an unrecognised value could be the highest, so bachelor + it is no FAIL."""
    assert ps05(with_degrees(data, "at", "วท.บ.")).status is REVIEW


def test_ps05_every_education_record_of_a_person_is_read(data):
    with_degrees(data, "วท.บ.")
    one = sorted(responsible(data), key=str)[0]
    data["educations"].append({"_id": oid(), "personId": one, "degree": "ปร.ด.", "field": "x"})
    items = [i for g in ps05(data).data_found for i in g.items]
    assert ps05(data).status is FAIL                                        # the other four hold a bachelor only
    assert sum("is at least 'master'" in i for i in items) == 1


def test_ps05_the_aliases_are_read_from_config(data):
    with_degrees(data, "ปร.ด.")
    del cfg(data, "PS-05")["degree"]["aliases"]["Ph.D."]
    assert ps05(data).status is REVIEW                                      # no longer a known form
    cfg(data, "PS-05")["degree"]["aliases"]["bachelor"].append("ปร.ด.")
    assert ps05(data).status is FAIL                                        # the configuration says what it ranks as


def test_ps05_the_normalization_is_read_from_config(data):
    with_degrees(data, "ปร. ด.")
    cfg(data, "PS-05")["degree"]["normalization"]["enabled"] = False
    assert ps05(data).status is REVIEW                                      # exact forms only
    cfg(data, "PS-05")["degree"]["normalization"]["enabled"] = True
    assert ps05(data).status is PASS


def test_ps05_the_result_names_each_value_and_what_it_stands_for(data):
    r = ps05(with_degrees(data, "ปร.ด.", "at"))
    assert all(i == "degree: at → not in the ordering; ปร.ด. → Ph.D. (highest 'Ph.D.' is at least 'master') -> PASS"
               for g in r.data_found for i in g.items)


# the five degree patterns of the real responsible lecturers (aunqa_ps, 2026-09-27), as test data
@pytest.mark.parametrize("values,detail", [
    (("ปร.ด.", "วท.บ.", "ปร.ด.", "วท.บ."),
     "degree: ปร.ด. → Ph.D.; วท.บ. → bachelor (highest 'Ph.D.' is at least 'master') -> PASS"),
    (("Ph.D.", "วท.ม.", "วท.บ.", "Ph.D."),
     "degree: Ph.D. → Ph.D.; วท.บ. → bachelor; วท.ม. → master (highest 'Ph.D.' is at least 'master') -> PASS"),
    (("วท.ม.", "บธ.บ."),
     "degree: บธ.บ. → bachelor; วท.ม. → master (highest 'master' is at least 'master') -> PASS"),
    (("วท.ม.", "วท.บ.", "วท.ม.", "วท.บ.", "heuristic approach. Journal of Sensor and Actuator", "at"),
     "degree: at → not in the ordering; heuristic approach. Journal of Sensor and Actuator → not in the ordering; "
     "วท.บ. → bachelor; วท.ม. → master (highest 'master' is at least 'master') -> PASS"),
    (("ปร.ด.", "วท.ม.", "วท.บ.", "วบ.บ."),
     "degree: ปร.ด. → Ph.D.; วท.บ. → bachelor; วท.ม. → master; วบ.บ. → bachelor (highest 'Ph.D.' is at least 'master') -> PASS"),
])
def test_ps05_the_highest_recognised_degree_of_all_records_decides(data, values, detail):
    r = ps05(with_degrees(data, *values))
    assert r.status is PASS and all(i == detail for g in r.data_found for i in g.items)


@pytest.mark.parametrize("values,expected", [
    (("วบ.บ.",), FAIL), (("วบ.บ.", "วท.ม."), PASS), (("วท.บ.", "บธ.บ.", "วบ.บ."), FAIL),
])
def test_ps05_the_owners_second_bachelor_form(data, values, expected):
    assert ps05(with_degrees(data, *values)).status is expected


def test_ps05_the_failing_detail_names_the_highest_and_the_minimum(data):
    r = ps05(with_degrees(data, "วท.บ.", "บธ.บ."))
    assert r.status is FAIL
    assert all(i.endswith("(highest 'bachelor' is below 'master') -> FAIL") for g in r.data_found for i in g.items)


# --- only the subjects the configuration selects are judged ---
def summary(r, label):
    return next((i.value for i in r.data_summary if i.label == label), None)


def test_ps05_judges_only_programme_responsible(data):
    """Staff members with a bachelor only, a malformed degree or no education do not enter PS-05."""
    add_person(data, "programmeStaff", degree="วท.บ.")
    add_person(data, "programmeStaff", degree="at")
    add_person(data, "programmeStaff", degree=None, field=None)
    r = ps05(data)
    assert r.status is PASS and summary(r, "Subjects") == "5" and summary(r, "Subjects PASS") == "5"
    judged = {t.values["personId"] for t in r.traceability if t.collection == "appointments"}
    assert judged == {str(p) for p in responsible(data)}


def test_ps05_the_judged_role_comes_from_config(data):
    staff = add_person(data, "programmeStaff", degree="วท.บ.")
    cfg(data, "PS-05")["appointment"]["role"] = "programmeStaff"
    r = ps05(data)
    assert summary(r, "Subjects") == "6" and r.status is FAIL                  # now the staff member is judged
    assert str(staff) in {t.values["personId"] for t in r.traceability if t.collection == "appointments"}


def test_ps05_educations_of_people_who_are_not_subjects_do_not_count(data):
    with_degrees(data, "วท.บ.")
    data["educations"].append({"_id": oid(), "personId": oid(), "degree": "ปร.ด.", "field": "x"})   # nobody's subject
    assert ps05(data).status is FAIL


@pytest.mark.parametrize("mutate", [
    lambda d: d.update(aliases={"doctorate": ["ปร.ด."]}),                  # not an ordering value
    lambda d: d.update(aliases={"bachelor": ["X1"], "master": ["x1"]}),     # one form, two values (case ignored)
    lambda d: d.update(aliases={"bachelor": ["Master"]}),                   # an alias that is another ordering value
    lambda d: d.update(aliases={"master": [". "]}),                         # nothing left after normalization
    lambda d: d.update(aliases=["ปร.ด."]),                                  # not an object
    lambda d: d.update(aliases={"master": "วท.ม."}),                        # not a list
    lambda d: d.update(aliases={"master": [5]}),
    lambda d: d.update(normalization="blanks"),                             # not an object
    lambda d: d.update(ordering=["bachelor", "Bachelor", "master", "Ph.D."]),   # the same value twice, case ignored
])
def test_ps05_an_inconsistent_alias_table_is_a_configuration_error(data, mutate):
    mutate(cfg(data, "PS-05")["degree"])
    r = ps05(with_degrees(data, "ปร.ด."))
    assert r.status is REVIEW and r.issue == "configuration_error"


def test_ps05_aliases_without_an_ordering_never_decide(data):
    del cfg(data, "PS-05")["degree"]["ordering"]
    r = ps05(with_degrees(data, "ปร.ด."))
    assert r.status is REVIEW and "SPEC GAP" in " ".join(r.missing_information)


# =============================== PS-05 on the real data ===============================
# DB-DATA/ holds the read-only export of aunqa_ps (2026-09-27; its source collections were checked equal to the live
# database). The source collections are read as exported; the configuration is the ACTIVE file, because the runtime
# ps_requirements of aunqa_ps does not have degree.aliases / normalization yet (the owner imports them).
REAL = Path(__file__).resolve().parents[2] / "DB-DATA"
REAL_CURRICULUM = "6ab0efb53ca5c474ff43f8da"
REAL_RESPONSIBLE = {"6ab0fb633ca5c474ff43f8dc", "6ab0fb633ca5c474ff43f8dd", "6ab0fb633ca5c474ff43f8de",
                    "6ab0fb633ca5c474ff43f8e1", "6ab0fb633ca5c474ff43f8e0"}   # the owner's list, for this test only


@pytest.mark.skipif(not (REAL / "educations.json").exists(), reason="the DB-DATA export of aunqa_ps is not present")
def test_ps05_on_the_real_data_of_the_curriculum():
    data = {c: json_util.loads((REAL / f"{c}.json").read_text(encoding="utf-8")) for c in SOURCE_SCHEMA}
    data["ps_requirements"] = copy.deepcopy(AUTHORITATIVE_CONFIG)
    assert [str(c["_id"]) for c in data["curricula"]] == [REAL_CURRICULUM]
    r = ps05(data)
    judged = {t.values["personId"] for t in r.traceability if t.collection == "appointments"}
    assert judged == REAL_RESPONSIBLE                                          # programmeResponsible only
    assert r.status is PASS and r.issue is None and r.missing_information == []
    assert (summary(r, "Subjects"), summary(r, "Subjects PASS"), summary(r, "Subjects FAIL"),
            summary(r, "Subjects REVIEW")) == ("5", "5", None, None)
    assert len(r.data_found) == 5 and all(i.endswith("-> PASS") for g in r.data_found for i in g.items)


# =============================== PS-07: years in either calendar ===============================
def ps07(data, references=CLOCK_2026):
    service, _ = make_service(data, references=references)
    return next(r for r in service.monitor().results if r.ps_code == "PS-07")


def every_year(data, value):
    for w in data["academic_works"]:
        w["publicationYear"] = value
    return data


@pytest.mark.parametrize("value,expected", [
    (2564, PASS), (2565, PASS), (2566, PASS), (2567, PASS), (2568, PASS), (2569, PASS),     # Buddhist era
    (2022, PASS), (2023, PASS), (2024, PASS), (2025, PASS), (2026, PASS),                   # Gregorian: +543
    (2021, PASS), (2020, FAIL),                                                             # 2564 / 2563
    (2563, FAIL), (2570, FAIL), (2027, FAIL),                                               # outside the window
    ("2567", PASS), (" 2025 ", PASS), ("2563", FAIL),                                       # text of digits
])
def test_ps07_years_in_either_calendar(data, value, expected):
    assert ps07(every_year(data, value)).status is expected


@pytest.mark.parametrize("value", [None, "", "  ", "n/a", "2567 BE", "25-67", True, 2567.0, [2567], {"y": 2567}])
def test_ps07_a_value_that_is_not_a_year_is_never_counted(data, value):
    r = ps07(every_year(data, value))
    assert r.status is REVIEW and "lack a usable publicationYear" in " ".join(r.missing_information)


def test_ps07_a_usable_year_satisfies_next_to_an_unusable_one(data):
    every_year(data, "n/a")
    for p in {a["personId"] for a in data["appointments"]}:
        data["academic_works"].append({"_id": oid(), "personId": p, "publicationYear": 2025})
    assert ps07(data).status is PASS


def test_ps07_a_missing_year_field_is_not_a_year(data):
    for w in data["academic_works"]:
        w.pop("publicationYear")
    assert ps07(data).status is REVIEW


def test_ps07_counts_per_person_after_conversion(data):
    """One staff member with Gregorian years only (2022-2024): counted in the window once converted."""
    add_person(data, "programmeStaff", works=(2022, 2023, 2024))
    r = ps07(data)
    assert r.status is PASS and any("3 in window" in i for g in r.data_found for i in g.items)
    add_person(data, "programmeStaff", works=(2019,))                      # 2562: outside
    assert ps07(data).status is FAIL


def test_ps07_no_conversion_when_the_data_calendar_is_gregorian(data):
    gregorian = RuntimeReferences(0, lambda: date(2026, 9, 27))           # window 2021-2026
    assert ps07(every_year(data, 2025), gregorian).status is PASS
    assert ps07(every_year(data, 2567), gregorian).status is FAIL


def test_ps07_a_source_without_a_calendar_converts_nothing(data):
    """The fixed test references carry no calendar: years are compared as stored (the behaviour before)."""
    assert results(every_year(data, 2025))["PS-07"].status is FAIL


# =============================== the pieces ===============================
@pytest.mark.parametrize("year,expected", [
    (2022, 2565), (2023, 2566), (2024, 2567), (2025, 2568), (2026, 2569),
    (2564, 2564), (2565, 2565), (2566, 2566), (2567, 2567), (2568, 2568), (2569, 2569),
    (2027, 2027), (2570, 2570),
])
def test_runtime_references_put_a_year_in_the_anchor_calendar(year, expected):
    assert CLOCK_2026.in_anchor_calendar(year) == expected


def test_with_no_offset_or_no_definition_a_year_is_kept():
    assert RuntimeReferences(0, lambda: date(2026, 9, 27)).in_anchor_calendar(2025) == 2025
    assert UndefinedReferences().in_anchor_calendar(2025) == 2025


@pytest.mark.parametrize("value,expected", [
    (2567, 2567), ("2567", 2567), (" 2025\t", 2025), (0, 0),
    (None, None), ("", None), ("n/a", None), ("-5", None), ("2567.0", None), (2567.0, None), (True, None),
])
def test_whole_number(value, expected):
    assert whole_number(value) == expected


# =============================== API (same contract) ===============================
def client_for(service):
    app = create_app()
    app.dependency_overrides[get_service] = lambda: service
    return TestClient(app)


def test_api_reports_the_engine_result_for_both(data):
    with_degrees(data, "at", "ปร.ด.")
    every_year(data, 2025)
    service, _ = make_service(data, references=CLOCK_2026)
    client = client_for(service)
    engine = {r.ps_code: r.status.value for r in service.monitor().results}
    body = client.get("/api/monitor").json()
    api = {r["psCode"]: r["status"] for r in body["results"]}
    assert api == engine and api["PS-05"] == "PASS" and api["PS-07"] == "PASS"
    for code in ("PS-05", "PS-07"):
        detail = client.get(f"/api/monitor/ps/{code}").json()
        assert detail["status"] == "PASS" and set(detail) == set(body["results"][0])   # same PSResult shape
