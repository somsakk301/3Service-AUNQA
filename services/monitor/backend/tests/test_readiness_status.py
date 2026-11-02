"""The status both readinesses count (project owner, 2026-09-27).

`PSResult.readiness_status()`: the reviewer's saved choice for a PS the configuration has reviewed by the user,
else the engine's status. The engine's `status` and the saved `review.status` stay two separate values; the
readiness status is worked out when readiness is computed and is neither serialized nor stored. Programme
Readiness stays PASS / 9 x 100; Generation Readiness applies its configured allowed / blocked statuses to it.
"""
import copy
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user, get_service
from app.main import create_app
from app.models.auth import AuthenticatedUser
from app.models.schemas import ProgrammeReadiness, UserReview
from app.models.status import Readiness, Status
from app.repositories.monitoring_results import MonitoringResultRepository
from tests.support.fixtures import GENERATION_READINESS, make_service
from tests.support.memory_store import InMemoryMonitoringResultAdapter

PASS, FAIL, REVIEW, NA = Status.PASS, Status.FAIL, Status.REVIEW, Status.NA
ALL = [f"PS-0{n}" for n in range(1, 10)]
TEST_USER = AuthenticatedUser(user_id="507f1f77bcf86cd799439011", name="ผู้ตรวจทดสอบ")


def results_of(data):
    return {r.ps_code: r for r in make_service(data)[0].monitor().results}


def with_review(result, status):
    return result.model_copy(update={"review": UserReview(allow_manual_result=[PASS, FAIL, REVIEW], status=status)})


def as_status(result, status):
    return result.model_copy(update={"status": status})


# --- CASE 1-5: the readiness status of one PS -------------------------------------------------------------------
@pytest.mark.parametrize("engine, review, expected", [
    (REVIEW, PASS, PASS),        # CASE 1
    (REVIEW, FAIL, FAIL),        # CASE 2
    (REVIEW, None, REVIEW),      # CASE 3: the review is offered, nothing saved yet
    (REVIEW, REVIEW, REVIEW),
])
def test_cases_1_2_3_a_reviewed_ps(data, engine, review, expected):
    r = with_review(as_status(results_of(data)["PS-03"], engine), review)
    assert r.readiness_status() is expected and r.status is engine            # the engine's status is untouched


@pytest.mark.parametrize("engine", [PASS, FAIL, REVIEW, NA])
def test_cases_4_5_a_ps_without_review_counts_the_engine_status(data, engine):
    r = as_status(results_of(data)["PS-01"], engine)
    assert r.review is None and r.readiness_status() is engine


# --- CASE 6: the formula stays PASS / 9 x 100 --------------------------------------------------------------------
def test_case6_eight_readiness_passes_of_nine_is_88_89(data):
    r = results_of(data)
    statuses = {"PS-01": PASS, "PS-02": PASS, "PS-03": REVIEW, "PS-04": PASS, "PS-05": PASS, "PS-06": FAIL,
                "PS-07": PASS, "PS-08": PASS, "PS-09": PASS}
    listed = [as_status(r[c], s) for c, s in statuses.items()]
    listed[2] = with_review(listed[2], PASS)                                   # PS-03: REVIEW + review PASS
    assert ProgrammeReadiness.of(listed).model_dump(by_alias=True) == {"percentage": 88.89, "passCount": 8, "totalPS": 9}
    listed[2] = with_review(listed[2], None)
    assert ProgrammeReadiness.of(listed).model_dump(by_alias=True) == {"percentage": 77.78, "passCount": 7, "totalPS": 9}


def test_case6_a_ps_still_counts_once(data):
    r = with_review(as_status(results_of(data)["PS-03"], REVIEW), PASS)
    assert ProgrammeReadiness.of([r, r]).pass_count == 1


# --- through the service, with the Monitor-owned store ------------------------------------------------------------
def store(docs=None):
    return InMemoryMonitoringResultAdapter(docs)


def service_for(data, adapter):
    return make_service(data, results=MonitoringResultRepository(adapter))[0]


def prepared(data):
    data["ps_requirements"].append(copy.deepcopy(GENERATION_READINESS))
    return data


def ps06_confirmed(service):
    """PS-06 is REVIEW until the user confirms it: confirmed PASS here, so PS-03 is the only PS still to review."""
    service.review("PS-06", "PASS")
    return service


def test_case7_the_engine_result_stays_review_after_a_pass_review(data):
    adapter = store()
    service = ps06_confirmed(service_for(prepared(data), adapter))
    before = service.monitor()
    service.review("PS-03", "PASS")
    after = service.monitor()
    ps03 = next(r for r in after.results if r.ps_code == "PS-03")
    assert (ps03.status, ps03.review.status, ps03.readiness_status()) == (REVIEW, PASS, PASS)
    assert [r.status for r in after.results] == [r.status for r in before.results]      # no engine status moved
    assert (before.programme_readiness.pass_count, after.programme_readiness.pass_count) == (7, 8)


def test_case8_generation_readiness_is_not_blocked_by_a_pass_reviewed_ps(data):
    service = ps06_confirmed(service_for(prepared(data), store()))
    assert [(b.ps_code, b.status) for b in service.monitor().generation_readiness.blocking_ps] == [("PS-03", REVIEW)]
    service.review("PS-03", "PASS")
    decided = service.monitor().generation_readiness
    assert decided.status is Readiness.READY and decided.blocking_ps == []
    service.review("PS-03", "FAIL")
    decided = service.monitor().generation_readiness
    assert decided.status is Readiness.NOT_READY and [(b.ps_code, b.status) for b in decided.blocking_ps] == [("PS-03", FAIL)]


def test_a_saved_review_counts_only_where_the_configuration_offers_one(data):
    """A review stored for a PS the configuration does not have reviewed by the user is never read."""
    cid = data["curricula"][0]["_id"]
    docs = [{"curriculumId": cid, "psCode": "PS-01",
             "review": {"status": "FAIL", "recordedAt": datetime.now(timezone.utc)}}]
    ps01 = next(r for r in service_for(data, store(docs)).monitor().results if r.ps_code == "PS-01")
    assert ps01.review is None and ps01.readiness_status() is PASS


def test_case9_no_readiness_status_is_stored_or_served(data):
    adapter = store()
    service = ps06_confirmed(service_for(prepared(data), adapter))
    service.review("PS-03", "PASS")
    service.save_results()
    stored = repr(adapter.docs)
    assert "effectiveStatus" not in stored and "readiness" not in stored.lower()
    ps03 = next(d for d in adapter.docs if d["psCode"] == "PS-03")
    assert ps03["review"]["status"] == "PASS" and ps03["result"]["status"] == "REVIEW"   # both kept apart
    app = create_app()
    app.dependency_overrides[get_service] = lambda: service
    body = TestClient(app).get("/api/monitor").json()
    served = next(r for r in body["results"] if r["psCode"] == "PS-03")
    assert "effectiveStatus" not in served and "readinessStatus" not in served
    assert (served["status"], served["review"]["status"]) == ("REVIEW", "PASS")
    assert body["programmeReadiness"] == {"percentage": 88.89, "passCount": 8, "totalPS": 9}
    assert body["generationReadiness"]["status"] == "READY"


def test_the_review_endpoint_moves_readiness_over_http(data):
    service = service_for(prepared(data), store())
    app = create_app()
    app.dependency_overrides[get_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: TEST_USER
    client = TestClient(app)
    assert client.get("/api/monitor").json()["programmeReadiness"]["passCount"] == 6          # PS-03, PS-06: REVIEW
    assert client.post("/api/monitor/ps/PS-06/review", json={"status": "PASS"}).status_code == 200
    assert client.get("/api/monitor").json()["programmeReadiness"]["passCount"] == 7
    assert client.post("/api/monitor/ps/PS-03/review", json={"status": "PASS"}).status_code == 200
    body = client.get("/api/monitor").json()
    assert (body["programmeReadiness"]["passCount"], body["generationReadiness"]["status"]) == (8, "READY")
    assert next(r for r in body["results"] if r["psCode"] == "PS-03")["status"] == "REVIEW"
    assert set(body) == {"curriculum", "overallStatus", "dataCompleteness", "results", "generationReadiness",
                         "programmeReadiness"}                                    # same response shape
