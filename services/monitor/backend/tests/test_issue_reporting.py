"""SRS §48/§50: a configuration error or a SPEC GAP is reported as such (`issue`), apart from an ordinary REVIEW.

The status is still the one the configuration provides for what cannot be decided; `issue` says *why*
nothing was decided, so a reviewer can tell "someone must look at the data" from "the configuration must be fixed".
"""
import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_service
from app.main import create_app
from app.models.status import Status
from tests.support.fixtures import ManualResults, add_person, make_service, results


def cfg(data, code):
    return next(d["config"] for d in data["ps_requirements"] if d["psCode"] == code)


def summary(r):
    return {i.label: i.value for i in r.data_summary}


def test_the_authoritative_configuration_raises_no_issue(data):
    assert {c: r.issue for c, r in results(data).items()} == {c: None for c in results(data)}


def test_a_configuration_error_is_reported_as_such(data):
    data["ps_requirements"][0]["config"] = {"result": {"review": "REVIEW"}, "count": {"field": 1}}   # malformed
    r = results(data)["PS-01"]
    assert r.status is Status.REVIEW and r.issue == "configuration_error"


def test_a_spec_gap_is_reported_as_such(data):
    cfg(data, "PS-04")["somethingNew"] = True
    r = results(data)["PS-04"]
    assert r.status is Status.REVIEW and r.issue == "spec_gap"


def test_a_configuration_error_is_reported_before_a_spec_gap(data):
    c = cfg(data, "PS-01")
    c["somethingNew"] = True                  # a gap ...
    c["targetCollection"] = "ps_requirements"  # ... and an error
    r = results(data)["PS-01"]
    assert r.issue == "configuration_error"
    assert any(m.startswith("SPEC GAP") for m in r.missing_information)


def test_a_gap_found_while_executing_is_a_spec_gap(data):
    r = results(data, year=None)["PS-09"]      # no reference value defined
    assert r.status is Status.REVIEW and r.issue == "spec_gap"


def test_a_gap_found_in_one_subject_is_a_spec_gap(data):
    del cfg(data, "PS-05")["degree"]["ordering"]
    for e in data["educations"]:
        e["degree"] = "Ph.D."                  # no ordering is defined for degree values
    r = results(data)["PS-05"]
    assert r.status is Status.REVIEW and r.issue == "spec_gap"


def test_a_review_caused_by_the_data_alone_raises_no_issue(data):
    for e in data["educations"]:
        e["field"] = None                      # PS-06: no qualification field to show the reviewer
    r = results(data)["PS-06"]
    assert r.status is Status.REVIEW and r.issue is None and r.missing_information


def test_a_review_the_configuration_asks_for_is_a_summary_note_not_missing_data(data):
    r = results(data)["PS-03"]
    assert r.status is Status.REVIEW and r.issue is None
    assert r.missing_information == [] and r.data_completeness == "complete"
    assert summary(r)["Review"] == "Review by user required by configuration"


def test_an_invalid_manual_choice_keeps_the_note_and_is_a_spec_gap(data):
    cfg(data, "PS-03")["review"]["allowManualResult"] = ["FAIL"]
    service, _ = make_service(data, manual=ManualResults({"PS-03": "PASS"}))
    r = next(x for x in service.monitor().results if x.ps_code == "PS-03")
    assert r.status is Status.REVIEW and r.issue == "spec_gap" and "Review" in summary(r)


def test_manual_review_needed_is_a_summary_note_not_missing_data(data):
    add_person(data, "specialInstructor")
    for block in ("qualification", "experience"):
        cfg(data, "PS-08")[block].pop("condition")                        # a configuration that states no criterion
    cfg(data, "PS-08")["experience"]["source"] = "educations.institution"   # a source exists: no gap
    r = results(data)["PS-08"]
    assert r.status is Status.REVIEW and r.issue is None
    assert summary(r)["Review"].startswith("Manual review required")
    assert not any("Manual review required" in m for m in r.missing_information)


@pytest.mark.parametrize("broken,expected", [(False, None), (True, "configuration_error")])
def test_the_api_sends_the_issue(data, broken, expected):
    if broken:
        cfg(data, "PS-01")["targetCollection"] = "ps_requirements"
    service, _ = make_service(data)
    app = create_app()
    app.dependency_overrides[get_service] = lambda: service
    client = TestClient(app)
    body = client.get("/api/monitor").json()
    assert next(r for r in body["results"] if r["psCode"] == "PS-01")["issue"] == expected
    assert client.get("/api/monitor/ps/PS-01").json()["issue"] == expected


def test_a_non_scalar_value_in_a_check_is_reported_not_a_crash(data):
    cfg(data, "PS-05")["degree"]["minimum"] = ["master", "doctor"]     # a list where a single value is expected
    r = results(data)["PS-05"]
    assert r.status is Status.REVIEW and r.issue == "configuration_error"   # not one of degree.ordering
    del cfg(data, "PS-05")["degree"]["ordering"]                       # without an ordering: equality only
    r = results(data)["PS-05"]
    assert r.status is Status.REVIEW and r.issue == "spec_gap"
