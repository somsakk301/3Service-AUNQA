"""PS-08 through the same pipeline as every other PS (project owner, 2026-09-28): Config -> Rule Engine -> API ->
readiness. In-memory adapters only (no database). The four outcomes come from the ACTIVE configuration in the
repository; no business rule is added or changed here.
"""
import copy
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_service
from app.main import create_app
from app.models.status import Status
from app.repositories.monitoring_results import MonitoringResultRepository
from tests.support.fixtures import GENERATION_READINESS, add_person, make_service
from tests.support.memory_store import InMemoryMonitoringResultAdapter

PASS, FAIL, REVIEW, NA = Status.PASS, Status.FAIL, Status.REVIEW, Status.NA


def special(data, *, degree="master", experience=True):
    pid = add_person(data, "specialInstructor", degree=degree)
    person = next(p for p in data["persons"] if p["_id"] == pid)
    if experience is not None:
        person["hasTeachingExperience"] = experience
    return pid


OUTCOMES = {
    "PASS": (lambda d: special(d), PASS),
    "FAIL": (lambda d: special(d, experience=False), FAIL),
    "REVIEW": (lambda d: special(d, experience=None), REVIEW),
    "N/A": (lambda d: None, NA),
}


def api(data, store=None):
    service, source = make_service(data, results=store)
    app = create_app()
    app.dependency_overrides[get_service] = lambda: service
    return TestClient(app), source


@pytest.mark.parametrize("name", OUTCOMES)
def test_the_four_outcomes_come_from_the_configuration_through_the_api(data, name):
    prepare, expected = OUTCOMES[name]
    prepare(data)
    client, source = api(data)
    body = client.get("/api/monitor").json()
    listed = next(r for r in body["results"] if r["psCode"] == "PS-08")
    detail = client.get("/api/monitor/ps/PS-08").json()
    assert listed["status"] == detail["status"] == expected.value
    assert {op for op, _ in source.calls} == {"find"}                      # read-only, in memory


@pytest.mark.parametrize("name", OUTCOMES)
def test_the_result_has_the_shape_of_every_other_ps(data, name):
    OUTCOMES[name][0](data)
    body = api(data)[0].get("/api/monitor").json()
    by = {r["psCode"]: r for r in body["results"]}
    ps08 = by["PS-08"]
    assert set(ps08) == set(by["PS-02"]) == set(by["PS-07"])               # same PSResult fields
    assert ps08["verification"]["found"] == len(ps08["traceability"])      # as for every PS
    labels = [i["label"] for i in ps08["dataSummary"]]
    assert labels[:2] == ["Operation", "Subjects"]                           # the subject-based summary of PS-02 / 05 / 06 / 07
    if name == "N/A":
        assert ps08["dataFound"] == [] and "Not applicable" in labels
    else:
        assert labels[2:] == [f"Subjects {name}"]
        assert [g["items"][-1].rsplit("-> ", 1)[1] for g in ps08["dataFound"]] == [name]


def test_what_is_missing_is_said_only_when_it_decides_a_review(data):
    special(data, experience=None)
    ps08 = api(data)[0].get("/api/monitor/ps/PS-08").json()
    assert ps08["missingInformation"] == ["experience: no value found for review"] and ps08["dataCompleteness"] == "incomplete"
    for name in ("PASS", "FAIL", "N/A"):
        d = copy.deepcopy(data)
        d["persons"] = [p for p in d["persons"] if p.get("fullName") != "y"]
        d["appointments"] = [a for a in d["appointments"] if a["role"] != "specialInstructor"]
        OUTCOMES[name][0](d)
        assert api(d)[0].get("/api/monitor/ps/PS-08").json()["missingInformation"] == []


# PS-03 and PS-06 are REVIEW until a user reviews them, so the other seven PS count six PASS
@pytest.mark.parametrize("name, counted", [("PASS", 7), ("FAIL", 6), ("REVIEW", 6), ("N/A", 6)])
def test_programme_readiness_counts_ps08_only_when_it_passes(data, name, counted):
    OUTCOMES[name][0](data)
    readiness = api(data)[0].get("/api/monitor").json()["programmeReadiness"]
    assert readiness == {"percentage": round(counted * 100 / 9, 2), "passCount": counted, "totalPS": 9}


@pytest.mark.parametrize("name, blocked", [("PASS", False), ("N/A", False), ("FAIL", True), ("REVIEW", True)])
def test_generation_readiness_applies_its_configured_statuses_to_ps08(data, name, blocked):
    data["ps_requirements"].append(copy.deepcopy(GENERATION_READINESS))
    OUTCOMES[name][0](data)
    decided = api(data)[0].get("/api/monitor").json()["generationReadiness"]
    assert ("PS-08" in {b["psCode"] for b in decided["blockingPS"]}) is blocked


def test_ps08_has_no_user_review_so_its_engine_status_is_the_readiness_status(data):
    """The PS-08 configuration has no review block: a review stored for it is never read."""
    special(data, experience=None)
    cid = data["curricula"][0]["_id"]
    docs = [{"curriculumId": cid, "psCode": "PS-08", "review": {"status": "PASS", "reviewedAt": datetime.now(timezone.utc)}}]
    store = MonitoringResultRepository(InMemoryMonitoringResultAdapter(docs))
    service, _ = make_service(data, results=store)
    ps08 = next(r for r in service.monitor().results if r.ps_code == "PS-08")
    assert ps08.review is None and ps08.readiness_status() is REVIEW is ps08.status
    assert service.monitor().programme_readiness.pass_count == 6        # PS-03 and PS-06: REVIEW, no user review
