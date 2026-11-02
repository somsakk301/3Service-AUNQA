"""The nine authoritative PS configurations, executed by the generic engine.

Every test goes Config -> Interpreter -> Generic Engine -> Data -> Result. Behaviour is varied
by changing the configuration or the data, never by naming a PS in code.
"""
import copy
import json
from pathlib import Path

import pytest

from app.models.status import Status
from tests.support.fixtures import (
    FixedReferences, ManualResults, add_person, appointment, make_service, oid, results,
)

ALL = [f"PS-0{i}" for i in range(1, 10)]
PASS, FAIL, REVIEW, NA = Status.PASS, Status.FAIL, Status.REVIEW, Status.NA


def status(data, code, **kw):
    return results(data, **kw)[code].status


def cfg(data, code):
    return next(d["config"] for d in data["ps_requirements"] if d["psCode"] == code)


def missing(data, code, **kw):
    return " | ".join(results(data, **kw)[code].missing_information)


def responsible(data):
    return [a for a in data["appointments"] if a["role"] == "programmeResponsible"]


def staff(data):
    return [a for a in data["appointments"] if a["role"] == "programmeStaff"]


def items(r):
    return [i for g in r.data_found for i in g.items]


# =============================== the authoritative configuration ===============================
def test_authoritative_config_has_nine_active_ps(data):
    assert [d["psCode"] for d in data["ps_requirements"]] == ALL
    assert all(d["active"] for d in data["ps_requirements"])


def test_all_nine_execute_from_configuration_and_none_is_a_spec_gap(data):
    r = results(data)
    assert {c: x.status for c, x in r.items()} == {
        "PS-01": PASS, "PS-02": PASS, "PS-03": REVIEW, "PS-04": PASS, "PS-05": PASS,
        "PS-06": REVIEW, "PS-07": PASS, "PS-08": NA, "PS-09": PASS}
    for code, x in r.items():
        assert not any("SPEC GAP" in m or "Configuration error" in m for m in x.missing_information), (code, x.missing_information)


def test_ps03_review_is_what_the_configuration_asks_for_not_a_gap(data):
    r = results(data)["PS-03"]
    assert r.review_required is True and r.review_by_user is True
    assert r.missing_information == [] and r.issue is None                   # a review is not missing data
    assert ("Review", "Review by user required by configuration") in {(i.label, i.value) for i in r.data_summary}


def test_every_ps_reports_what_was_read_and_the_operation_it_ran(data):
    for code, r in results(data).items():
        assert any(i.label == "Operation" for i in r.data_summary), code
        if code != "PS-08":                       # PS-08 selects no subject in this data
            assert r.traceability and r.verification.found == len(r.traceability), code


def test_authoritative_config_with_no_reference_defined_only_affects_the_ps_that_need_one(data):
    r = results(data, year=None)
    assert r["PS-09"].status is REVIEW and "SPEC GAP" in " ".join(r["PS-09"].missing_information)
    assert r["PS-07"].status is REVIEW and "SPEC GAP" in " ".join(r["PS-07"].missing_information)
    assert all(r[c].status is not REVIEW for c in ("PS-01", "PS-02", "PS-04", "PS-05"))


# =============================== PS-01: filter + distinct count + condition ===============================
def test_ps01_threshold_from_config(data):
    assert status(data, "PS-01") is Status.PASS
    data["appointments"].remove(responsible(data)[0])
    assert status(data, "PS-01") is Status.FAIL
    cfg(data, "PS-01")["condition"]["value"] = 4
    assert status(data, "PS-01") is Status.PASS


def test_ps01_operator_from_config(data):
    cfg(data, "PS-01")["condition"]["operator"] = ">"
    assert status(data, "PS-01") is Status.FAIL          # 5 > 5 is false


def test_ps01_counts_distinct_persons_in_this_curriculum(data):
    data["appointments"].append({**responsible(data)[0], "_id": oid()})
    data["appointments"].append(appointment(oid(), oid(), "programmeResponsible"))   # another curriculum
    r = results(data)["PS-01"]
    assert r.status is Status.PASS and "5" in [i.value for i in r.data_summary]


def test_ps01_distinct_flag_from_config(data):
    data["appointments"].append({**responsible(data)[0], "_id": oid()})
    cfg(data, "PS-01")["count"]["distinct"] = False
    cfg(data, "PS-01")["condition"]["value"] = 6
    assert status(data, "PS-01") is Status.PASS


def test_ps01_count_field_from_config(data):
    for a in responsible(data):
        a["roleName"] = "same"
    cfg(data, "PS-01")["count"]["field"] = "roleName"
    assert status(data, "PS-01") is Status.FAIL          # 1 distinct roleName < 5


def test_ps01_filter_from_config(data):
    cfg(data, "PS-01")["filter"]["role"] = "programmeStaff"
    data["appointments"] = [a for a in data["appointments"] if a["role"] == "programmeStaff"][:4]
    assert status(data, "PS-01") is Status.FAIL


def test_ps01_record_without_the_counted_field_is_review_and_spec_gap(data):
    responsible(data)[0]["personId"] = None
    r = results(data)["PS-01"]
    assert r.status is Status.REVIEW and r.data_completeness == "incomplete"
    assert any(m.startswith("SPEC GAP") and "personId" in m for m in r.missing_information)


def test_ps01_no_records_counts_zero_and_uses_the_configured_fail(data):
    data["appointments"] = []
    assert status(data, "PS-01") is Status.FAIL


def test_ps01_result_mapping_comes_from_config(data):
    data["appointments"].remove(responsible(data)[0])
    cfg(data, "PS-01")["result"]["fail"] = "REVIEW"
    assert status(data, "PS-01") is Status.REVIEW


def test_ps01_reports_the_operation_it_executed(data):
    r = results(data)["PS-01"]
    op = next(i.value for i in r.data_summary if i.label == "Operation")
    assert "personId" in op and "appointments" in op and "programmeResponsible" in op and ">= 5" in op


def test_filter_and_count_run_on_any_source_collection_with_a_declared_curriculum_link(data):
    cid = data["curricula"][0]["_id"]
    data["documents"] = [{"_id": oid(), "curriculumId": cid, "documentType": "cv", "fileName": f"f{i}"} for i in range(3)]
    c = cfg(data, "PS-01")
    c.update(targetCollection="documents", filter={"documentType": "cv"}, count={"field": "fileName", "distinct": True})
    c["condition"]["value"] = 3
    assert status(data, "PS-01") is Status.PASS
    c["condition"]["value"] = 4
    assert status(data, "PS-01") is Status.FAIL


def test_collection_without_a_declared_curriculum_relationship_is_a_spec_gap(data):
    cfg(data, "PS-01")["targetCollection"] = "educations"
    r = results(data)["PS-01"]
    assert r.status is Status.REVIEW and "no relationship" in " ".join(r.missing_information)


# =============================== PS-02: subjects + match keys + EXISTS ===============================
def test_ps02_every_subject_needs_a_related_record(data):
    assert status(data, "PS-02") is PASS
    data["appointments"].remove(staff(data)[0])
    r = results(data)["PS-02"]
    assert r.status is FAIL and "0 matching record(s) -> FAIL" in items(r)


def test_ps02_same_curriculum_key_from_config(data):
    staff(data)[0]["curriculumId"] = oid()
    assert status(data, "PS-02") is FAIL


def test_ps02_same_person_key_from_config(data):
    staff(data)[0]["personId"] = oid()
    assert status(data, "PS-02") is FAIL
    del cfg(data, "PS-02")["matching"]["samePerson"]      # without that key the persons are no longer compared
    assert status(data, "PS-02") is PASS


def test_ps02_both_roles_come_from_config(data):
    c = cfg(data, "PS-02")
    c["permanentRole"] = c["condition"]["field"] = "specialInstructor"
    assert status(data, "PS-02") is FAIL
    add_person(data, "specialInstructor")                 # not the same people, but present
    assert status(data, "PS-02") is FAIL


def test_ps02_condition_must_name_the_related_role(data):
    cfg(data, "PS-02")["condition"]["field"] = "somethingElse"
    r = results(data)["PS-02"]
    assert r.status is REVIEW and "EXISTS needs one filter" in " ".join(r.missing_information)


def test_ps02_without_subjects_nothing_can_be_checked(data):
    data["appointments"] = [a for a in data["appointments"] if a["role"] != "programmeResponsible"]
    r = results(data)["PS-02"]
    assert r.status is REVIEW and r.data_completeness == "incomplete"      # naEnabled is false


def test_ps02_subjects_are_grouped_by_the_match_keys(data):
    data["appointments"].append({**responsible(data)[0], "_id": oid()})    # same person twice
    r = results(data)["PS-02"]
    assert r.status is PASS and next(i.value for i in r.data_summary if i.label == "Subjects") == "5"


# =============================== PS-03: review by user ===============================
def named(data):
    for i, p in enumerate(data["persons"]):
        p["fullName"] = f"name-{i}"
    return {p["_id"]: p["fullName"] for p in data["persons"]}


def test_ps03_shows_the_records_the_reviewer_needs(data):
    names = named(data)
    r = results(data)["PS-03"]
    assert r.status is REVIEW
    group = next(g for g in r.data_found if g.label == "appointments")
    assert sorted(group.items) == sorted(names[a["personId"]] for a in responsible(data))      # shown by name
    assert {t.collection for t in r.traceability} == {"appointments"} and r.verification.found == 5
    assert {t.record_id for t in r.traceability} == {str(a["_id"]) for a in responsible(data)}  # traced by record


def test_ps03_target_role_from_config(data):
    names = named(data)
    data["appointments"] = [a for a in data["appointments"] if a["role"] == "programmeResponsible"
                            or a["personId"] == data["persons"][0]["_id"]]                # one staff record left
    cfg(data, "PS-03")["targetRole"] = "programmeStaff"
    r = results(data)["PS-03"]
    assert next(g for g in r.data_found).items == [names[data["persons"][0]["_id"]]]
    assert {t.record_id for t in r.traceability} == {str(a["_id"]) for a in staff(data)}


@pytest.mark.parametrize("chosen", ["PASS", "FAIL", "REVIEW"])
def test_ps03_manual_result_within_allowManualResult_is_used(data, chosen):
    service, _ = make_service(data, manual=ManualResults({"PS-03": chosen}))
    r = next(x for x in service.monitor().results if x.ps_code == "PS-03")
    assert r.status is Status(chosen)


def test_ps03_manual_result_outside_allowManualResult_is_rejected(data):
    cfg(data, "PS-03")["review"]["allowManualResult"] = ["FAIL"]
    service, _ = make_service(data, manual=ManualResults({"PS-03": "PASS"}))
    r = next(x for x in service.monitor().results if x.ps_code == "PS-03")
    assert r.status is REVIEW and "not among the configured allowManualResult" in " ".join(r.missing_information)


def test_ps03_review_status_is_the_configured_one(data):
    cfg(data, "PS-03")["result"]["review"] = "FAIL"
    assert status(data, "PS-03") is FAIL


def test_ps03_invalid_allowManualResult_is_a_spec_gap(data):
    cfg(data, "PS-03")["review"]["allowManualResult"] = ["MAYBE"]
    assert "allowManualResult" in missing(data, "PS-03")


def test_review_without_required_true_has_no_defined_meaning(data):
    cfg(data, "PS-03")["review"]["required"] = False
    assert "no defined meaning" in missing(data, "PS-03")


# =============================== PS-04: required fields, nested fields, <field>Required ===============================
@pytest.mark.parametrize("break_it", [
    lambda a: a["appointmentOrder"].pop("orderNumber"),
    lambda a: a["appointmentOrder"].update(orderDate=""),
    lambda a: a.pop("appointmentOrder"),
    lambda a: a.pop("roleName"),
    lambda a: a.update(role=None),
])
def test_ps04_missing_required_data_is_the_configured_fail(data, break_it):
    break_it(responsible(data)[0])
    r = results(data)["PS-04"]
    assert r.status is FAIL and r.missing_information and any("missing" in i for i in items(r))


def test_ps04_complete_data_passes(data):
    r = results(data)["PS-04"]
    assert r.status is PASS and r.missing_information == []
    assert "appointmentOrder.orderNumber" in next(i.value for i in r.data_summary if i.label == "Operation")


def test_ps04_roleNameRequired_makes_the_field_required_by_itself(data):
    cfg(data, "PS-04")["requiredFields"].remove("roleName")       # only the flag asks for it now
    data["appointments"][0].pop("roleName")
    assert status(data, "PS-04") is FAIL
    del cfg(data, "PS-04")["role"]["roleNameRequired"]
    assert status(data, "PS-04") is PASS


def test_ps04_roleNameRequired_false_requires_nothing(data):
    cfg(data, "PS-04")["requiredFields"].remove("roleName")
    cfg(data, "PS-04")["role"]["roleNameRequired"] = False
    data["appointments"][0].pop("roleName")
    assert "no defined meaning" in missing(data, "PS-04")


def test_ps04_flag_naming_an_undeclared_field_is_a_spec_gap(data):
    cfg(data, "PS-04")["role"]["nothingRequired"] = True
    assert "not a field" in missing(data, "PS-04")


def test_ps04_no_records_is_the_configured_fail(data):
    data["appointments"] = []
    r = results(data)["PS-04"]
    assert r.status is FAIL and r.data_completeness == "incomplete"


def test_ps04_field_list_comes_from_config(data):
    data["appointments"][0].pop("roleName")
    cfg(data, "PS-04")["requiredFields"].remove("roleName")
    del cfg(data, "PS-04")["role"]["roleNameRequired"]
    assert status(data, "PS-04") is PASS
    cfg(data, "PS-04")["appointmentOrder"]["requiredFields"].append("orderDate")
    data["appointments"][1]["appointmentOrder"].pop("orderDate")
    assert status(data, "PS-04") is FAIL


# =============================== PS-05: join + at-least ===============================
def test_ps05_value_equal_to_the_configured_minimum_passes(data):
    r = results(data)["PS-05"]
    assert r.status is PASS and all("is at least 'master'" in i for i in items(r))


# --- degree.ordering (the project owner's config, 2026-09-25): bachelor < master < Ph.D., minimum master ---
def degrees(data, value):
    for e in data["educations"]:
        if value is None:
            e.pop("degree", None)
        else:
            e["degree"] = value


@pytest.mark.parametrize("value,expected", [
    ("bachelor", FAIL), ("master", PASS), ("Ph.D.", PASS),
    (None, REVIEW), ("", REVIEW),                                  # missing
    ("Diploma", REVIEW), ("Master", REVIEW), ("PhD", REVIEW),      # not in the ordering: matched exactly, never guessed
])
def test_ps05_degree_is_compared_by_the_configured_ordering(data, value, expected):
    # the ordering alone (no aliases / normalization configured): values must equal an ordering value exactly.
    # With the ACTIVE config's normalization (2026-09-27) "Master" and "PhD" do rank: test_degree_and_year_forms.py
    for key in ("aliases", "normalization"):
        cfg(data, "PS-05")["degree"].pop(key)
    degrees(data, value)
    r = results(data)["PS-05"]
    assert r.status is expected and r.issue is None                # a decided or data-caused result raises no issue


def test_ps05_missing_and_unlisted_degrees_say_what_is_missing(data):
    degrees(data, None)
    assert "no usable degree value" in missing(data, "PS-05")
    degrees(data, "Diploma")
    assert "not in the configured ordering: Diploma" in missing(data, "PS-05")


def test_ps05_the_highest_listed_degree_of_a_person_counts(data):
    degrees(data, "bachelor")
    people = {a["personId"] for a in responsible(data)}
    plus = lambda value: {**data, "educations": data["educations"] + [   # noqa: E731
        {"_id": oid(), "personId": p, "degree": value, "field": "x"} for p in people]}
    assert status(plus("Ph.D."), "PS-05") is PASS                  # bachelor + Ph.D. -> Ph.D.
    assert status(plus("Diploma"), "PS-05") is REVIEW              # bachelor + an unlisted value: cannot be a fail


def test_ps05_ordering_is_read_from_config(data):
    degrees(data, "bachelor")
    cfg(data, "PS-05")["degree"]["ordering"] = ["master", "bachelor", "Ph.D."]
    assert status(data, "PS-05") is PASS                           # bachelor now ranks above master
    degrees(data, "Diploma")
    assert status(data, "PS-05") is REVIEW
    cfg(data, "PS-05")["degree"]["ordering"] = ["Diploma", "bachelor", "master", "Ph.D."]
    assert status(data, "PS-05") is FAIL                           # listed now, below master


def test_ps05_minimum_comes_from_config(data):
    cfg(data, "PS-05")["degree"]["minimum"] = "Ph.D."
    assert status(data, "PS-05") is FAIL                           # master is below Ph.D.
    degrees(data, "Ph.D.")
    assert status(data, "PS-05") is PASS
    cfg(data, "PS-05")["degree"]["minimum"] = "bachelor"
    degrees(data, "bachelor")
    assert status(data, "PS-05") is PASS


@pytest.mark.parametrize("mutate", [
    lambda d: d.update(minimum="doctorate"),                       # not one of the ordering
    lambda d: d.update(ordering=["bachelor", "master", "master"]), # duplicates
    lambda d: d.update(ordering=[]),
    lambda d: d.update(ordering="bachelor, master"),               # not a list
])
def test_ps05_an_inconsistent_ordering_is_a_configuration_error(data, mutate):
    mutate(cfg(data, "PS-05")["degree"])
    r = results(data)["PS-05"]
    assert r.status is REVIEW and r.issue == "configuration_error"


def test_ps05_without_an_ordering_only_equality_with_the_minimum_is_decidable(data):
    for key in ("ordering", "aliases", "normalization"):           # a configuration that defines no ordering
        del cfg(data, "PS-05")["degree"][key]
    for e in data["educations"]:
        e["degree"] = "Ph.D."
    r = results(data)["PS-05"]
    assert r.status is REVIEW
    assert any(m.startswith("SPEC GAP") and "no ordering of degree" in m for m in r.missing_information)
    assert FAIL not in {r.status}


def test_ps05_any_of_a_persons_educations_may_satisfy(data):
    pid = responsible(data)[0]["personId"]
    data["educations"].append({"_id": oid(), "personId": pid, "degree": "Ph.D.", "field": "x"})
    assert status(data, "PS-05") is PASS


def test_ps05_every_subject_must_be_decided(data):
    data["educations"] = [e for e in data["educations"] if e["personId"] != responsible(data)[0]["personId"]]
    r = results(data)["PS-05"]
    assert r.status is REVIEW and "no usable degree value" in " ".join(r.missing_information)


def test_ps05_join_uses_the_configured_fields_and_ignores_unrelated_records(data):
    data["educations"].append({"_id": oid(), "personId": oid(), "degree": "Ph.D.", "field": "x"})   # nobody's subject
    other = oid()
    data["appointments"].append(appointment(oid(), other, "programmeResponsible"))                  # another curriculum
    r = results(data)["PS-05"]
    assert r.status is PASS and next(i.value for i in r.data_summary if i.label == "Subjects") == "5"


def test_ps05_traceability_names_collections_records_and_fields(data):
    r = results(data)["PS-05"]
    by = {(t.collection): t for t in r.traceability}
    assert set(by) == {"appointments", "educations"}
    assert "role" in by["appointments"].fields and by["educations"].values["degree"] == "master"


def test_ps05_role_filter_comes_from_config(data):
    cfg(data, "PS-05")["appointment"]["role"] = "specialInstructor"
    assert status(data, "PS-05") is REVIEW                     # no such subjects


# =============================== PS-06: user confirmation, nothing decided automatically ===============================
# The configuration asks the user to decide (review.reviewByUser, allowManualResult PASS / FAIL) and names what the
# reviewer is shown: every responsible lecturer and the degree, field and institution of their educations.
APP = Path(__file__).resolve().parent.parent / "app"
MAPPING_WORDS = ("mapping", "Mapping", "related", "approved", "aliases", "normalization", "extract")


def field_of(data, value):
    for e in data["educations"]:
        e["field"] = value


def test_ps06_configuration_is_a_user_review_with_no_mapping(data):
    c = cfg(data, "PS-06")
    assert c["review"] == {"required": True, "reviewByUser": True, "allowManualResult": ["PASS", "FAIL"]}
    text = json.dumps(c, ensure_ascii=False)
    assert not [w for w in MAPPING_WORDS if w in text], text


def test_ps06_is_review_until_the_user_confirms(data):
    r = results(data)["PS-06"]
    assert r.status is REVIEW and r.issue is None and r.missing_information == []
    assert r.review_required is True and r.review_by_user is True
    assert ("Review", "Review by user required by configuration") in {(i.label, i.value) for i in r.data_summary}


def test_ps06_shows_each_responsible_lecturer_and_the_qualifications_found(data):
    r = results(data)["PS-06"]
    assert len(r.data_found) == len(responsible(data))                    # one group per lecturer
    for g in r.data_found:
        assert g.items == ["qualification: master -> REVIEW", "qualificationField: Computer Science -> REVIEW",
                           "institution: x -> REVIEW"]
    assert {t.collection for t in r.traceability} >= {"appointments", "educations"}


@pytest.mark.parametrize("value", ["Computer Science", "Information Technology", "Biology", "Accounting",
                                   "สาขาวิชาวิทยาการคอมพิวเตอร์", "วิทยาศาสตร์เชิงคำนวณ"])
def test_ps06_never_decides_from_the_field_of_study(data, value):
    field_of(data, value)
    r = results(data)["PS-06"]
    assert r.status is REVIEW and r.issue is None
    assert f"qualificationField: {value} -> REVIEW" in items(r) and all(i.endswith("-> REVIEW") for i in items(r))


@pytest.mark.parametrize("name", ["วิทยาศาสตรบัณฑิต สาขาวิชาชีววิทยา", "Bachelor of Arts in History", ""])
def test_ps06_the_curriculum_name_is_not_matched_and_raises_no_configuration_error(data, name):
    data["curricula"][0]["curriculumName"] = name
    r = results(data)["PS-06"]
    assert r.status is REVIEW and r.issue is None and r.missing_information == []


def test_ps06_a_missing_field_of_study_is_shown_as_missing_never_decided(data):
    field_of(data, None)
    r = results(data)["PS-06"]
    assert r.status is REVIEW and r.issue is None
    assert "qualificationField: no value found for review" in r.missing_information


def test_ps06_a_lecturer_without_any_education_is_shown_not_failed(data):
    lecturer = responsible(data)[0]["personId"]
    data["educations"] = [e for e in data["educations"] if e["personId"] != lecturer]
    r = results(data)["PS-06"]
    assert r.status is REVIEW and r.issue is None
    assert "qualification: no value found for review" in r.missing_information


def test_ps06_no_responsible_lecturer_is_a_review_for_missing_data_not_a_configuration_error(data):
    for a in responsible(data):
        data["appointments"].remove(a)
    r = results(data)["PS-06"]
    assert r.status is REVIEW and r.issue is None
    assert not any(m.startswith("Configuration error") for m in r.missing_information)
    assert "nothing can be checked" in " ".join(r.missing_information)


def test_ps06_a_responsible_appointment_without_personid_is_a_review_not_a_configuration_error(data):
    record = {k: v for k, v in responsible(data)[0].items() if k != "personId"}
    data["appointments"].append({**record, "_id": oid()})
    r = results(data)["PS-06"]
    assert r.status is REVIEW and r.issue is None
    assert "lack" in " ".join(r.missing_information)


def test_ps06_a_reviewed_join_that_would_decide_is_a_spec_gap(data):
    cfg(data, "PS-06")["qualificationField"]["condition"] = {"operator": "==", "value": "Computer Science"}
    r = results(data)["PS-06"]
    assert r.status is REVIEW and r.issue == "spec_gap"
    assert "may only show information" in missing(data, "PS-06")


def test_ps06_the_former_automatic_configuration_decides_nothing(data):
    """The PS-06 configuration from before the user confirmation (a comparison of the curriculum name with the field
    of study): the engine has no such operation any more, so it never gives PASS or FAIL and reports a SPEC GAP."""
    c = cfg(data, "PS-06")
    for key in ("review", "qualification", "qualificationField", "institution"):
        del c[key]
    c.update({"programmeField": {"source": "curricula.curriculumName", "method": "extract"},
              "qualificationField": {"source": "educations.field"},
              "comparison": {"method": "mapping", "allowExactMatch": True, "allowRelatedMatch": True},
              "fieldMappings": [{"programmeField": "วิทยาการคอมพิวเตอร์", "aliases": ["Computer Science"]}],
              "result": {"exact": "PASS", "related": "PASS", "unrelated": "FAIL", "unknown": "REVIEW"}})
    r = results(data)["PS-06"]
    assert r.status is REVIEW and r.issue == "spec_gap"
    assert "no technical definition for" in missing(data, "PS-06")


def test_no_automatic_mapping_remains_in_the_application():
    assert not (APP / "monitoring" / "mapping.py").exists()
    source = "\n".join(p.read_text() for p in APP.rglob("*.py"))
    for word in ("fieldMappings", "relatedFields", "allowExactMatch", "allowRelatedMatch", "MappingCheck",
                 "MappingEntry", "find_entry", "classify(", "unicodedata"):
        assert word not in source, word


# =============================== PS-07: join + time window + count per subject ===============================
def test_ps07_window_and_minimum_come_from_config(data):
    assert status(data, "PS-07") is PASS                       # works in 2569, reference 2569
    for w in data["academic_works"]:
        w["publicationYear"] = 2563                            # 6 years back
    assert status(data, "PS-07") is FAIL
    cfg(data, "PS-07")["publicationYear"]["period"] = "previous6Years"
    assert status(data, "PS-07") is PASS
    cfg(data, "PS-07")["minimumCount"] = 2
    assert status(data, "PS-07") is FAIL


@pytest.mark.parametrize("year,expected", [(2564, PASS), (2569, PASS), (2563, FAIL), (2570, FAIL)])
def test_ps07_window_boundaries(data, year, expected):
    for w in data["academic_works"]:
        w["publicationYear"] = year
    assert status(data, "PS-07") is expected


def test_ps07_reference_value_comes_from_the_reference_source(data):
    service, _ = make_service(data, references=FixedReferences({"currentYear": 2575}))
    assert next(r for r in service.monitor().results if r.ps_code == "PS-07").status is FAIL


def test_ps07_the_anchor_name_is_the_reference_sources_business(data):
    near = FixedReferences({"someOtherName": 2569}, anchor="someOtherName")
    far = FixedReferences({"someOtherName": 2580, "currentYear": 2569}, anchor="someOtherName")   # 'currentYear' is not used
    for refs, expected in ((near, PASS), (far, FAIL)):
        service, _ = make_service(copy.deepcopy(data), references=refs)
        assert next(r for r in service.monitor().results if r.ps_code == "PS-07").status is expected


def test_ps07_counts_per_subject_not_in_total(data):
    data["academic_works"] = [w for w in data["academic_works"] if w["personId"] != responsible(data)[0]["personId"]]
    assert status(data, "PS-07") is FAIL                       # 4 works in total would satisfy a total of 1


def test_ps07_roles_come_from_config(data):
    pid = add_person(data, "programmeStaff", works=())         # a subject with no work
    assert status(data, "PS-07") is FAIL
    cfg(data, "PS-07")["targetRoles"] = ["programmeResponsible"]
    assert status(data, "PS-07") is PASS


def test_ps07_works_of_persons_who_are_not_subjects_do_not_count(data):
    data["academic_works"] = [{**w, "personId": oid()} for w in data["academic_works"]]
    assert status(data, "PS-07") is FAIL


def test_ps07_unusable_year_cannot_be_decided(data):
    pid = responsible(data)[0]["personId"]
    for w in data["academic_works"]:
        if w["personId"] == pid:
            w["publicationYear"] = None
    r = results(data)["PS-07"]
    assert r.status is REVIEW and "lack a usable publicationYear" in " ".join(r.missing_information)


def test_ps07_a_usable_work_still_satisfies_when_another_is_unusable(data):
    pid = responsible(data)[0]["personId"]
    data["academic_works"].append({"_id": oid(), "personId": pid, "publicationYear": "n/a"})
    assert status(data, "PS-07") is PASS


def test_ps07_without_a_defined_reference_is_a_spec_gap(data):
    r = results(data, year=None)["PS-07"]
    assert r.status is REVIEW and "needs a reference value" in " ".join(r.missing_information)


def test_ps07_unsupported_period_is_a_spec_gap(data):
    cfg(data, "PS-07")["publicationYear"]["period"] = "lastDecade"
    assert "publicationYear.period" in missing(data, "PS-07")


# =============================== PS-08 ===============================
# The project owner's rule (2026-09-25): a special instructor passes with a qualification (some educations.degree)
# and persons.hasTeachingExperience == true; nothing else about experience is judged. Without the two `condition`
# blocks (review_only) the configuration states no criterion: Mornitor gathers and shows, the user decides.
def special(data, **kw):
    return add_person(data, "specialInstructor", **kw)


def review_only(data):
    for block in ("qualification", "experience"):
        cfg(data, "PS-08")[block].pop("condition", None)


def ps08(data, manual=None):
    service, _ = make_service(data, manual=ManualResults({"PS-08": manual}) if manual else None)
    return next(r for r in service.monitor().results if r.ps_code == "PS-08")


def test_ps08_no_special_instructor_is_not_applicable_when_the_configuration_enables_it(data):
    r = results(data)["PS-08"]
    assert r.status is NA and r.missing_information == [] and r.data_completeness == "complete"


def test_ps08_naEnabled_false_in_config_gives_the_review_status_instead(data):
    cfg(data, "PS-08")["naEnabled"] = False
    r = results(data)["PS-08"]
    assert r.status is REVIEW and r.data_completeness == "incomplete"


def test_ps08_na_status_comes_from_the_result_map(data):
    cfg(data, "PS-08")["result"]["na"] = "REVIEW"
    assert status(data, "PS-08") is REVIEW
    del cfg(data, "PS-08")["result"]["na"]
    assert "result.na" in missing(data, "PS-08")


def test_ps08_na_is_not_a_manual_choice_and_does_not_replace_the_no_subject_case(data):
    assert ps08(data, manual="PASS").status is NA                       # nobody to review: a manual result is moot


def test_ps08_without_conditions_a_special_instructor_is_a_review_until_the_user_decides(data):
    review_only(data)
    special(data)
    r = ps08(data)
    assert r.status is REVIEW
    assert any(i.label == "Review" and i.value.startswith("Manual review required") for i in r.data_summary)


@pytest.mark.parametrize("degree", ["master", "Ph.D.", "Bachelor", "anything at all", "", None])
def test_ps08_without_conditions_no_degree_value_decides_anything_automatically(data, degree):
    review_only(data)
    special(data, degree=degree)
    r = ps08(data)
    assert r.status is REVIEW and r.status not in (PASS, FAIL)


def test_ps08_without_conditions_no_education_or_experience_data_is_still_a_review(data):
    review_only(data)
    special(data, degree=None, field=None)
    r = ps08(data)
    assert r.status is REVIEW and any("no value found" in m for m in r.missing_information)


@pytest.mark.parametrize("chosen", ["PASS", "FAIL", "REVIEW"])
@pytest.mark.parametrize("degree", ["master", "Ph.D.", None])
def test_ps08_the_users_choice_is_the_result_whatever_the_degree(data, chosen, degree):
    review_only(data)
    special(data, degree=degree)
    assert ps08(data, manual=chosen).status is Status(chosen)           # Ph.D. can be FAIL, master can be PASS: the user decides


def test_ps08_the_users_choice_is_recorded_in_the_summary(data):
    review_only(data)
    special(data)
    r = ps08(data, manual="PASS")
    assert ("Manual result", "PASS") in {(i.label, i.value) for i in r.data_summary}
    assert not any("Manual review required" in m for m in r.missing_information)


def test_ps08_a_choice_the_configuration_does_not_name_is_rejected(data):
    review_only(data)
    special(data)
    for bad in ("N/A", "MAYBE"):
        r = ps08(data, manual=bad)
        assert r.status is REVIEW and "not among the statuses the configuration names" in " ".join(r.missing_information)


def test_ps08_the_allowed_choices_come_from_the_configuration(data):
    review_only(data)
    special(data)
    del cfg(data, "PS-08")["conditions"]["insufficientInformation"]      # REVIEW is no longer a named outcome
    assert ps08(data, manual="PASS").status is PASS
    r = ps08(data, manual="REVIEW")
    assert r.status is REVIEW and "not among the statuses" in " ".join(r.missing_information)


def test_ps08_shows_the_data_the_configuration_points_at(data):
    special(data, degree="Ph.D.")
    r = ps08(data)
    shown = [i for g in r.data_found for i in g.items]
    assert "qualification: Ph.D." in " ".join(shown) and "experience: no value found" in " ".join(shown)   # no CV processed yet
    edu = next(t for t in r.traceability if t.collection == "educations")
    assert edu.values["degree"] == "Ph.D."                               # traceable to the record and field


def test_ps08_several_values_are_all_shown_and_none_is_ranked(data):
    pid = special(data, degree="master")
    data["educations"].append({"_id": oid(), "personId": pid, "degree": "Ph.D.", "field": "x"})
    r = ps08(data)
    assert r.status is REVIEW and "qualification: Ph.D., master" in " ".join(i for g in r.data_found for i in g.items)


def test_ps08_experience_data_appears_only_when_the_configuration_names_a_source(data):
    special(data, institution="Somewhere")
    cfg(data, "PS-08")["experience"]["source"] = None                          # a configuration that names no source
    assert any("experience: no data source" in i for g in ps08(data).data_found for i in g.items)
    assert any("SPEC GAP" in m and "experience.source is null" in m for m in ps08(data).missing_information)
    cfg(data, "PS-08")["experience"]["source"] = "educations.institution"     # a declared field, named by the config
    r = ps08(data)
    assert r.status is REVIEW                                              # shown, still not judged
    assert any("experience: Somewhere" in i for g in r.data_found for i in g.items)
    assert not any("experience.source is null" in m for m in r.missing_information)
    cfg(data, "PS-08")["experience"]["source"] = "educations.notDeclared"
    assert "experience.source is not a field" in missing(data, "PS-08")


# --- persons.hasTeachingExperience (Import Service SRS: persons, Boolean, absent until a CV is processed) ---
def with_experience_source(data):
    cfg(data, "PS-08")["experience"]["source"] = "persons.hasTeachingExperience"   # what the config owner would set


def person(data, pid):
    return next(p for p in data["persons"] if p["_id"] == pid)


@pytest.mark.parametrize("value,shown", [(True, "experience: true"), (False, "experience: false")])
def test_ps08_without_conditions_experience_from_the_referenced_record_is_shown_never_judged(data, value, shown):
    review_only(data)
    pid = special(data)
    person(data, pid)["hasTeachingExperience"] = value
    with_experience_source(data)
    r = ps08(data)
    assert r.status is REVIEW and r.issue is None                               # still the reviewer's decision
    assert any(shown in i for i in items(r))
    assert not any("experience" in m for m in r.missing_information)
    traced = next(t for t in r.traceability if t.collection == "persons")
    assert traced.record_id == str(pid) and traced.values["hasTeachingExperience"] == shown.split(": ")[1]


def test_ps08_experience_not_yet_recorded_is_missing_information_not_a_gap(data):
    special(data)                                                             # no hasTeachingExperience field
    with_experience_source(data)
    r = ps08(data)
    assert r.status is REVIEW and r.issue is None
    assert any("experience: no value found" in i for i in items(r))
    assert "experience: no value found for review" in r.missing_information


def test_ps08_experience_source_does_not_change_not_applicable_or_the_users_choice(data):
    review_only(data)
    with_experience_source(data)
    assert ps08(data).status is NA                                           # nobody to check
    pid = special(data)
    person(data, pid)["hasTeachingExperience"] = False
    assert ps08(data, manual="PASS").status is PASS                          # the user decides, not the value


def test_ps08_a_source_the_subjects_do_not_reference_is_a_spec_gap(data):
    special(data)
    cfg(data, "PS-08")["experience"]["source"] = "academic_works.title"
    r = ps08(data)
    assert r.status is REVIEW and r.issue == "spec_gap" and "experience.source is not a field" in " ".join(r.missing_information)


def test_ps08_a_configuration_without_an_experience_source_reports_the_gap(data):
    special(data)
    cfg(data, "PS-08")["experience"]["source"] = None                        # as PS-Config-v1 had it
    r = ps08(data)
    assert r.issue == "spec_gap" and any("experience.source is null" in m for m in r.missing_information)


def test_ps08_the_project_configuration_reads_experience_from_persons(data):
    """The project config names persons.hasTeachingExperience, reached through appointments.personId -> persons._id
    (Data Schema REFERENCES): no join key, no persons.personId field."""
    assert cfg(data, "PS-08")["experience"]["source"] == "persons.hasTeachingExperience"
    assert set(cfg(data, "PS-08")["join"].values()) == {"appointments.personId", "educations.personId"}
    pid = special(data)
    person(data, pid)["hasTeachingExperience"] = True
    r = ps08(data)
    assert r.status is PASS and r.issue is None and r.missing_information == []
    assert any("experience: true" in i for i in items(r))
    traced = next(t for t in r.traceability if t.collection == "persons")
    assert traced.record_id == str(pid) and traced.values["hasTeachingExperience"] == "true"
    assert set(traced.fields) == {"_id", "hasTeachingExperience"}             # joined on persons._id


# --- the owner's rule: has a qualification AND hasTeachingExperience == true ---
NO_EDUCATION = {"degree": None, "field": None}      # add_person then creates no educations record
BLANK_DEGREE = {"degree": None}                     # an educations record without a degree


@pytest.mark.parametrize("education,experience,expected", [
    ({}, True, PASS),                               # 2. qualification + experience
    (NO_EDUCATION, True, FAIL),                     # 3. no qualification
    ({}, False, FAIL),                              # 4. no experience
    ({}, "absent", REVIEW),                         # 5. experience not recorded (CV not processed)
    ({}, None, REVIEW),                             # 5. experience null
    ({}, "yes", REVIEW),                            # 5. not a Boolean: cannot be checked
    (BLANK_DEGREE, True, REVIEW),                   # 6. education record without a degree
    ({"degree": "Bachelor"}, True, PASS),           # any degree is a qualification: its level is not judged here
    (NO_EDUCATION, "absent", FAIL),                 # a fail is a fail even when other data is missing
    (BLANK_DEGREE, False, FAIL),
])
def test_ps08_qualification_exists_and_teaching_experience_is_true(data, education, experience, expected):
    pid = special(data, **education)
    if experience != "absent":
        person(data, pid)["hasTeachingExperience"] = experience
    r = ps08(data)
    assert r.status is expected and r.issue is None


def test_ps08_what_is_missing_is_said(data):
    special(data, **BLANK_DEGREE)
    assert missing(data, "PS-08") == "qualification: no value found for review | experience: no value found for review"
    data["persons"][-1]["hasTeachingExperience"] = "yes"
    assert "experience: yes cannot be compared with true" in missing(data, "PS-08")


def test_ps08_a_decided_result_needs_no_manual_review(data):
    pid = special(data)
    person(data, pid)["hasTeachingExperience"] = True
    r = ps08(data, manual="FAIL")
    assert r.status is PASS                                               # the configured conditions decide
    assert not any(i.label == "Review" for i in r.data_summary)


def test_ps08_every_special_instructor_must_pass(data):
    person(data, special(data))["hasTeachingExperience"] = True
    assert ps08(data).status is PASS
    special(data)                                                         # a second one, experience not recorded
    assert ps08(data).status is REVIEW
    person(data, special(data))["hasTeachingExperience"] = False          # a third one without experience
    assert ps08(data).status is FAIL


def test_ps08_the_conditions_come_from_the_configuration(data):
    person(data, special(data))["hasTeachingExperience"] = False
    assert ps08(data).status is FAIL
    cfg(data, "PS-08")["experience"]["condition"] = {"operator": "==", "value": False}
    assert ps08(data).status is PASS
    cfg(data, "PS-08")["experience"]["condition"] = {"operator": "EXISTS"}
    assert ps08(data).status is PASS                                      # recorded at all


@pytest.mark.parametrize("condition", [{"operator": "=="}, {"operator": "LIKE", "value": True},
                                       {"operator": "==", "value": [True]}, "EXISTS", {"operator": "EXISTS", "value": 1}])
def test_ps08_a_malformed_condition_is_a_configuration_error(data, condition):
    special(data)
    cfg(data, "PS-08")["experience"]["condition"] = condition
    r = ps08(data)
    assert r.status is REVIEW and r.issue == "configuration_error"


def test_ps08_the_source_fields_come_from_the_configuration(data):
    special(data, degree="master", field="Physics")
    cfg(data, "PS-08")["qualification"]["source"] = "educations.field"
    assert any("qualification: Physics" in i for g in ps08(data).data_found for i in g.items)


def test_ps08_role_comes_from_config(data):
    special(data)
    cfg(data, "PS-08")["targetRole"] = "programmeStaff"
    assert ps08(data).status is REVIEW
    cfg(data, "PS-08")["targetRole"] = "nobodyHasThis"
    assert ps08(data).status is NA


def test_ps08_every_subject_is_shown_and_one_choice_covers_the_requirement(data):
    review_only(data)
    special(data, degree="master")
    special(data, degree=None, field=None)
    r = ps08(data)
    assert r.status is REVIEW and next(i.value for i in r.data_summary if i.label == "Subjects") == "2"
    assert ps08(data, manual="FAIL").status is FAIL


def test_ps08_information_that_is_not_required_is_not_shown_and_nothing_remains_to_review(data):
    special(data)
    cfg(data, "PS-08")["qualification"]["required"] = False
    cfg(data, "PS-08")["experience"]["required"] = False
    r = ps08(data)
    assert r.status is REVIEW and "the configuration states nothing" in " ".join(r.missing_information)


# =============================== PS-09: formula + reference + comparison ===============================
def test_ps09_boundary_from_config(data):
    data["curricula"][0]["curriculumYear"] = 2564   # 5
    assert status(data, "PS-09") is Status.PASS
    data["curricula"][0]["curriculumYear"] = 2563   # 6
    assert status(data, "PS-09") is Status.FAIL
    cfg(data, "PS-09")["comparison"]["value"] = 6
    assert status(data, "PS-09") is Status.PASS


def test_ps09_operator_from_config(data):
    data["curricula"][0]["curriculumYear"] = 2564
    cfg(data, "PS-09")["comparison"]["operator"] = "<"
    assert status(data, "PS-09") is Status.FAIL


def test_ps09_reference_name_is_resolved_by_the_reference_port_not_by_code(data):
    c = cfg(data, "PS-09")
    c["comparison"]["reference"] = "anotherName"
    c["calculation"]["formula"] = "anotherName - curriculumYear"
    assert status(data, "PS-09") is Status.REVIEW                                   # 'anotherName' not defined
    service, _ = make_service(data, references=FixedReferences({"anotherName": 2569}))
    assert next(r for r in service.monitor().results if r.ps_code == "PS-09").status is Status.PASS


def test_ps09_field_and_formula_come_from_config(data):
    data["curricula"][0]["version"] = 2569 - 9
    c = cfg(data, "PS-09")
    c["year"]["field"] = "version"
    c["calculation"]["formula"] = "currentYear - version"
    assert status(data, "PS-09") is Status.FAIL


def test_ps09_without_a_defined_reference_is_review_never_pass_or_fail(data):
    r = results(data, year=None)["PS-09"]
    assert r.status is Status.REVIEW
    assert any(m.startswith("SPEC GAP") and "currentYear" in m for m in r.missing_information)
    assert any(i.value == "2567" for i in r.data_summary)          # the data it did read


def test_ps09_missing_or_non_integer_value_is_review(data):
    for value in (None, "2567", True):
        data["curricula"][0]["curriculumYear"] = value
        r = results(data)["PS-09"]
        assert r.status is Status.REVIEW and any("not an integer" in m for m in r.missing_information)


@pytest.mark.parametrize("formula", ["currentYear * curriculumYear", "other - curriculumYear", "currentYear -", "(currentYear)"])
def test_ps09_formula_the_engine_cannot_execute_is_a_spec_gap(data, formula):
    cfg(data, "PS-09")["calculation"]["formula"] = formula
    r = results(data)["PS-09"]
    assert r.status is Status.REVIEW and r.missing_information[0].startswith("SPEC GAP")


def test_ps09_unsupported_operator_is_a_spec_gap(data):
    cfg(data, "PS-09")["comparison"]["operator"] = "~="
    assert results(data)["PS-09"].missing_information[0].startswith("SPEC GAP")


# =============================== the generic operations, exercised through PS-04 ===============================
def test_the_configured_result_map_is_used_for_every_outcome(data):
    data["appointments"][0].pop("roleName")
    cfg(data, "PS-04")["result"]["fail"] = "REVIEW"
    assert status(data, "PS-04") is REVIEW
    cfg(data, "PS-04")["result"]["pass"] = "N/A"
    data["appointments"][0]["roleName"] = "x"
    assert status(data, "PS-04") is NA


def test_status_mapping_that_is_not_a_status_is_a_configuration_error(data):
    data["appointments"][0].pop("roleName")
    cfg(data, "PS-04")["result"]["fail"] = "MAYBE"
    assert "Configuration error" in missing(data, "PS-04")


def test_na_is_not_defined_for_an_operation_without_subjects(data):
    cfg(data, "PS-01")["naEnabled"] = True
    assert "not-applicable" in missing(data, "PS-01")
