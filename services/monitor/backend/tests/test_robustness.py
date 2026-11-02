"""One malformed configuration or record never takes the whole monitor down (SRS §48: Configuration Error and
Evaluation Error are reported per PS; only a data-source failure stops the run, as 503)."""
import random

import pytest
from bson import ObjectId

from app.models.status import Status
from app.monitoring import capabilities
from app.repositories.base import DataSourceError
from tests.support.fixtures import add_person, base_data, make_service, results


def cfg(data, code):
    return next(d["config"] for d in data["ps_requirements"] if d["psCode"] == code)


@pytest.mark.parametrize("code,mutate", [
    ("PS-01", lambda c: c.update(targetCollection=["appointments"])),      # a list where a name is expected
    ("PS-01", lambda c: c["condition"].update(value="5")),                   # text where a number is expected
    ("PS-09", lambda c: c["comparison"].update(value="5")),
    ("PS-07", lambda c: c.update(minimumCount=1.5)),
])
def test_a_malformed_value_is_a_configuration_error_of_that_ps_only(data, code, mutate):
    mutate(cfg(data, code))
    r = results(data)
    assert r[code].status is Status.REVIEW and r[code].issue == "configuration_error"
    assert all(x.issue is None for c, x in r.items() if c != code)


def test_non_text_values_in_the_configuration_are_shown_not_a_crash(data):
    cfg(data, "PS-01")["note"] = ObjectId()                                   # not something JSON can write
    data["ps_requirements"][0]["requirement"] = ["not", "text"]
    cfg(data, "PS-03")["review"]["required"] = ["x"]
    r = results(data)
    assert r["PS-01"].issue == "spec_gap" and r["PS-03"].issue == "spec_gap" and r["PS-03"].review_required is None
    assert any("note:" in line for line in r["PS-01"].checks)


def test_non_text_values_in_conditions_are_ignored_as_choices(data):
    add_person(data, "specialInstructor")
    cfg(data, "PS-08")["conditions"]["odd"] = ["PASS"]
    assert results(data)["PS-08"].status is Status.REVIEW


@pytest.mark.parametrize("bad", [["x"], {"a": 1}])
def test_a_record_with_a_non_scalar_key_is_unusable_not_a_crash(data, bad):
    data["appointments"][0]["personId"] = bad
    r = results(data)
    assert r["PS-01"].status is Status.REVIEW and r["PS-01"].issue == "spec_gap"      # cannot be counted
    assert r["PS-02"].status is Status.REVIEW and r["PS-05"].status is Status.REVIEW    # cannot be grouped


def test_an_unexpected_failure_is_an_evaluation_error_of_that_ps_only(data, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("unexpected")
    monkeypatch.setattr(capabilities, "evaluate_formula", boom)
    r = results(data)
    assert r["PS-09"].status is Status.REVIEW and r["PS-09"].issue == "evaluation_error"
    assert any(m.startswith("Evaluation error: RuntimeError") for m in r["PS-09"].missing_information)
    assert r["PS-01"].status is Status.PASS


def test_a_data_source_failure_still_stops_the_run(data, monkeypatch):
    def down(*a, **k):
        raise DataSourceError("connection refused")
    monkeypatch.setattr(capabilities, "evaluate_formula", down)
    service, _ = make_service(data)
    with pytest.raises(DataSourceError):
        service.monitor()


WEIRD = [None, "", [], {}, ["x"], {"a": 1}, True, False, 0, 2567, "2567", "Ph.D.", ObjectId(), 3.5]


@pytest.mark.parametrize("seed", range(300))
def test_random_malformed_configuration_and_data_never_crash_the_monitor(seed):
    rnd = random.Random(seed)
    data = base_data()
    if rnd.random() < 0.5:
        add_person(data, "specialInstructor")
        cfg(data, "PS-08")["experience"]["source"] = rnd.choice(["persons.hasTeachingExperience", None, "educations.institution"])
    for _ in range(rnd.randint(1, 6)):
        coll = rnd.choice([c for c in data if c != "ps_requirements" and data[c]])
        doc = rnd.choice(data[coll])
        key = rnd.choice(list(doc) + ["hasTeachingExperience", "fullName"])
        if key != "_id":
            doc[key] = rnd.choice(WEIRD)
    c = rnd.choice(data["ps_requirements"])["config"]
    k = rnd.choice(list(c))
    if isinstance(c[k], dict) and c[k]:
        c[k][rnd.choice(list(c[k]))] = rnd.choice(WEIRD)
    else:
        c[k] = rnd.choice(WEIRD)
    service, _ = make_service(data)
    assert len(service.monitor().results) == 9


def test_a_list_as_target_collection_of_a_required_fields_check_is_a_configuration_error(data):
    cfg(data, "PS-04")["targetCollection"] = ["appointments"]
    r = results(data)["PS-04"]
    assert r.status is Status.REVIEW and r.issue == "configuration_error"
