"""PS-06 by user confirmation (project owner / lecturer, 2026-09-29).

The engine never decides whether a lecturer's qualification relates to the curriculum: PS-06 is REVIEW and the
reviewer confirms PASS ("มีความสัมพันธ์") or FAIL ("ไม่มีความสัมพันธ์") through the existing User Review endpoint.
The choice is kept in `monitoring_results.review`; the engine's `status` and the persisted `result` stay REVIEW,
and both readinesses count the resolved status (`PSResult.readiness_status()`).
"""
import copy
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user, get_service
from app.main import create_app
from app.models.auth import AuthenticatedUser
from app.models.status import Readiness, Status
from app.repositories.monitoring_results import MonitoringResultRepository
from tests.support.fixtures import GENERATION_READINESS, make_service
from tests.support.memory_store import InMemoryMonitoringResultAdapter

T1 = datetime(2026, 9, 29, 5, 0, tzinfo=timezone.utc)
REVIEW_URL = "/api/monitor/ps/{}/review"
PASS, FAIL, REVIEW, NA = Status.PASS, Status.FAIL, Status.REVIEW, Status.NA
OTHERS = ["PS-01", "PS-02", "PS-03", "PS-04", "PS-05", "PS-07", "PS-08", "PS-09"]
TEST_USER = AuthenticatedUser(user_id="507f1f77bcf86cd799439011", name="ผู้ตรวจทดสอบ")
RECORDED_BY = {"userId": TEST_USER.user_id, "name": TEST_USER.name}


def prepared(data):
    data["ps_requirements"].append(copy.deepcopy(GENERATION_READINESS))
    return data


def setup(data):
    adapter = InMemoryMonitoringResultAdapter()
    service, _ = make_service(prepared(data), results=MonitoringResultRepository(adapter, lambda: T1))
    app = create_app()
    app.dependency_overrides[get_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: TEST_USER
    return service, adapter, TestClient(app)


def ps06(body):
    return next(r for r in body["results"] if r["psCode"] == "PS-06")


def blocking(body):
    return [(b["psCode"], b["status"]) for b in body["generationReadiness"]["blockingPS"]]


# --- before any confirmation ---------------------------------------------------------------------------------
def test_before_confirmation_ps06_is_review_and_offers_pass_or_fail(data):
    _, adapter, c = setup(data)
    r = c.get("/api/monitor/ps/PS-06").json()
    assert r["status"] == "REVIEW" and r["issue"] is None
    assert r["review"] == {"allowManualResult": ["PASS", "FAIL"], "status": None, "recordedBy": None, "recordedAt": None}
    assert adapter.docs == []


def test_before_confirmation_ps06_blocks_generation_and_is_not_counted(data):
    service, _, c = setup(data)
    service.review("PS-03", "PASS")                                   # PS-03 decided, so PS-06 is what is left
    body = c.get("/api/monitor").json()
    assert blocking(body) == [("PS-06", "REVIEW")] and body["generationReadiness"]["status"] == "NOT_READY"
    assert body["programmeReadiness"]["passCount"] == 7


# --- the reviewer's confirmation -----------------------------------------------------------------------------
@pytest.mark.parametrize("chosen", ["PASS", "FAIL"])
def test_the_confirmation_is_stored_as_the_review_and_the_engine_result_stays_review(data, chosen):
    service, adapter, c = setup(data)
    r = c.post(REVIEW_URL.format("PS-06"), json={"status": chosen})
    assert r.status_code == 200
    assert r.json()["status"] == "REVIEW"                                           # the engine's result
    assert r.json()["review"] == {"allowManualResult": ["PASS", "FAIL"], "status": chosen,
                                  "recordedBy": RECORDED_BY, "recordedAt": "2026-09-29T05:00:00Z"}
    cid = data["curricula"][0]["_id"]
    assert adapter.docs == [{"curriculumId": cid, "psCode": "PS-06",
                             "review": {"status": chosen, "recordedAt": T1, "recordedBy": RECORDED_BY}}]
    listed = ps06(c.get("/api/monitor").json())
    assert (listed["status"], listed["review"]["status"]) == ("REVIEW", chosen)


def test_review_is_not_a_choice_for_ps06(data):
    _, adapter, c = setup(data)
    assert c.post(REVIEW_URL.format("PS-06"), json={"status": "REVIEW"}).status_code == 422
    assert c.post(REVIEW_URL.format("PS-06"), json={"status": "N/A"}).status_code == 422
    assert adapter.docs == []


@pytest.mark.parametrize("chosen, resolved", [(None, REVIEW), ("PASS", PASS), ("FAIL", FAIL)])
def test_the_resolved_status_is_the_confirmation_else_review(data, chosen, resolved):
    service, _, _ = setup(data)
    if chosen:
        service.review("PS-06", chosen)
    r = next(x for x in service.monitor().results if x.ps_code == "PS-06")
    assert r.status is REVIEW and r.readiness_status() is resolved


# --- both readinesses count the resolved status ----------------------------------------------------------------
@pytest.mark.parametrize("chosen, counted, readiness, blocked", [
    ("PASS", 8, "READY", []),
    ("FAIL", 7, "NOT_READY", [("PS-06", "FAIL")]),
])
def test_both_readinesses_follow_the_confirmation(data, chosen, counted, readiness, blocked):
    service, _, c = setup(data)
    service.review("PS-03", "PASS")
    assert c.post(REVIEW_URL.format("PS-06"), json={"status": chosen}).status_code == 200
    body = c.get("/api/monitor").json()
    assert body["programmeReadiness"] == {"percentage": round(counted * 100 / 9, 2), "passCount": counted, "totalPS": 9}
    assert (body["generationReadiness"]["status"], blocking(body)) == (readiness, blocked)


# --- nothing else moves ---------------------------------------------------------------------------------------
@pytest.mark.parametrize("chosen", ["PASS", "FAIL"])
def test_a_confirmation_changes_no_other_ps(data, chosen):
    service, _, _ = setup(data)
    before = {r.ps_code: r for r in service.monitor().results}
    service.review("PS-06", chosen)
    after = {r.ps_code: r for r in service.monitor().results}
    for code in OTHERS:
        assert after[code].model_dump() == before[code].model_dump(), code
    assert after["PS-06"].model_dump(exclude={"review"}) == before["PS-06"].model_dump(exclude={"review"})


def test_the_saved_monitoring_result_keeps_the_engine_review_next_to_the_confirmation(data):
    service, adapter, c = setup(data)
    c.post(REVIEW_URL.format("PS-06"), json={"status": "PASS"})
    assert c.post("/api/monitor/results").status_code == 200
    doc = next(d for d in adapter.docs if d["psCode"] == "PS-06")
    assert doc["review"] == {"status": "PASS", "recordedAt": T1, "recordedBy": RECORDED_BY}
    assert doc["result"] == {"status": "REVIEW", "evaluatedAt": T1}
    served = ps06(c.get("/api/monitor").json())
    assert (served["status"], served["review"]["status"], served["persistedResult"]["status"]) == ("REVIEW", "PASS", "REVIEW")
