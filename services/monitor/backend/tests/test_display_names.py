"""Records are shown by name, not by ObjectId. DISPLAY ONLY: names never change a result and are not evidence.

The reference fields and the field that names a record come from `models/source_schema.py`
(Data Dictionary relationships), never from the evaluation code.
"""
import copy

from app.models.status import Status
from tests.support.fixtures import add_person, results


def name_people(data):
    names = {}
    for i, p in enumerate(data["persons"]):
        p["fullName"] = f"อาจารย์ {chr(ord('A') + i)}"
        names[p["_id"]] = p["fullName"]
    return names


def all_items(r):
    return [i for g in r.data_found for i in g.items]


def test_counted_references_are_shown_by_name(data):
    names = name_people(data)
    r = results(data)["PS-01"]
    assert sorted(all_items(r)) == sorted(names.values())
    assert not any(str(pid) in " ".join(all_items(r)) for pid in names)


def test_subjects_are_labelled_by_name(data):
    names = name_people(data)
    for code in ("PS-05", "PS-06", "PS-07"):
        r = results(data)[code]
        assert sorted(g.label for g in r.data_found) == sorted(names.values()), code


def test_the_key_that_scopes_subjects_to_the_monitored_curriculum_is_not_repeated_in_labels(data):
    names = name_people(data)
    r = results(data)["PS-02"]               # subjects are grouped by (curriculumId, personId)
    assert sorted(g.label for g in r.data_found) == sorted(names.values())


def test_records_shown_for_review_are_named(data):
    names = name_people(data)
    r = results(data)["PS-03"]
    assert sorted(all_items(r)) == sorted(names.values())


def test_a_reference_without_a_named_record_shows_the_id_and_says_what_is_missing(data):
    names = name_people(data)
    lost = data["persons"].pop(0)["_id"]
    r = results(data)["PS-01"]
    assert f"{lost} (ไม่พบ persons.fullName)" in all_items(r)
    assert len(all_items(r)) == len(names)


def test_two_records_with_the_same_name_stay_distinguishable(data):
    name_people(data)
    first, second = data["persons"][0], data["persons"][1]
    second["fullName"] = first["fullName"]
    items = all_items(results(data)["PS-01"])
    assert f"{first['fullName']} ({first['_id']})" in items and f"{second['fullName']} ({second['_id']})" in items


def test_names_never_change_a_status(data):
    named = copy.deepcopy(data)
    name_people(named)
    add_person(named, "specialInstructor")
    unnamed = copy.deepcopy(named)
    unnamed["persons"] = []
    a, b = results(named), results(unnamed)
    assert {c: r.status for c, r in a.items()} == {c: r.status for c, r in b.items()}
    assert a["PS-01"].status is Status.PASS


def test_name_lookups_are_not_evidence(data):
    name_people(data)
    r = results(data)["PS-01"]
    assert {t.collection for t in r.traceability} == {"appointments"}
    assert r.verification.found == len(r.traceability)


def test_records_checked_one_by_one_are_named_and_keep_their_id(data):
    names = name_people(data)
    appt = next(a for a in data["appointments"] if a["role"] == "programmeResponsible")
    del appt["appointmentOrder"]["orderNumber"]
    r = results(data)["PS-04"]
    label = f"{names[appt['personId']]} ({appt['_id']})"            # several records per name: the id stays
    assert f"{label}: missing appointmentOrder.orderNumber" in all_items(r)
    assert f"{label}: appointmentOrder.orderNumber" in r.missing_information


def test_a_record_with_its_own_name_field_is_shown_by_it(data):
    r = results(data)["PS-09"]
    assert [g.label for g in r.data_found] == [data["curricula"][0]["curriculumCode"]]
