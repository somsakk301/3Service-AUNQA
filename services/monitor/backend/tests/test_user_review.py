"""PS-03 User Review + persistence (SET 5, project owner 2026-09-26; recordedBy/recordedAt + session
authentication, project owner 2026-10-04).

The configuration of PS-03 asks for a review by the user (review.required, review.reviewByUser,
review.allowManualResult [PASS, FAIL, REVIEW]). The reviewer's choice is saved in `monitoring_results`
(curriculumId + psCode, `review: {status, recordedBy, recordedAt}`) and read back by GET as `review`. It is kept
apart from the result: the PS status stays the engine's and no readiness reads the choice (project owner's
decision). `client_for()` signs every request in as TEST_USER by default: this file is about review
persistence, not about authentication itself (see test_authentication.py for login/session behaviour).
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
from tests.support.fixtures import AUTHORITATIVE_CONFIG, GENERATION_READINESS, make_service, oid
from tests.support.memory_store import InMemoryMonitoringResultAdapter

T1 = datetime(2026, 9, 26, 5, 0, tzinfo=timezone.utc)
T2 = datetime(2026, 9, 26, 6, 0, tzinfo=timezone.utc)
T3 = datetime(2026, 9, 26, 7, 0, tzinfo=timezone.utc)
REVIEW = "/api/monitor/ps/{}/review"
VERIFY = "/api/monitor/ps/{}/verification"
CODES = [f"PS-0{n}" for n in range(1, 10)]
TEST_USER = AuthenticatedUser(user_id="507f1f77bcf86cd799439011", name="ผู้ตรวจทดสอบ")
RECORDED_BY = {"userId": TEST_USER.user_id, "name": TEST_USER.name}
# the PS the ACTIVE configuration has reviewed by the user (PS-03, and PS-06 since its user confirmation)
REVIEWED = {d["psCode"]: d["config"]["review"]["allowManualResult"] for d in AUTHORITATIVE_CONFIG
            if d["config"].get("review", {}).get("reviewByUser") is True}


class Clock:
    def __init__(self, *times):
        self.times = list(times)

    def __call__(self):
        return self.times.pop(0) if len(self.times) > 1 else self.times[0]


def prepared(data):
    data["ps_requirements"].append(copy.deepcopy(GENERATION_READINESS))
    data["documents"] = [{"_id": oid(), "documentType": "curriculum", "fileType": "pdf", "fileName": "TEST-1.pdf",
                          "curriculumId": data["curricula"][0]["_id"],
                          "originalFile": {"storage": "local", "path": "test-data/documents/original/TEST-1.pdf"}}]
    return data


def service_with_store(data, docs=None, fail=False, clock=None):
    adapter = InMemoryMonitoringResultAdapter(docs, fail)
    service, _ = make_service(data, results=MonitoringResultRepository(adapter, clock or Clock(T1, T2, T3)))
    return service, adapter


def client_for(service, user=TEST_USER):
    app = create_app()
    app.dependency_overrides[get_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def cfg(data, code):
    return next(d["config"] for d in data["ps_requirements"] if d.get("psCode") == code)


# --- configuration --------------------------------------------------------------------------------
def test_the_ps03_configuration_asks_for_a_user_review(data):
    assert cfg(data, "PS-03")["review"] == {"required": True, "reviewByUser": True,
                                            "allowManualResult": ["PASS", "FAIL", "REVIEW"]}


# --- TEST 01: GET shows the review of PS-03 only ---------------------------------------------------------
def test_01_only_the_ps_reviewed_by_the_user_carry_the_review(data):
    assert REVIEWED == {"PS-03": ["PASS", "FAIL", "REVIEW"], "PS-06": ["PASS", "FAIL"]}
    service, _ = service_with_store(prepared(data))
    body = client_for(service).get("/api/monitor").json()
    reviews = {r["psCode"]: r["review"] for r in body["results"]}
    for code, allowed in REVIEWED.items():
        assert reviews.pop(code) == {"allowManualResult": allowed, "status": None, "recordedBy": None, "recordedAt": None}
    assert set(reviews.values()) == {None}


def test_the_options_and_who_takes_a_review_come_from_the_configuration(data):
    cfg(data, "PS-03")["review"]["allowManualResult"] = ["PASS", "REVIEW"]
    cfg(data, "PS-01")["review"] = {"required": True, "reviewByUser": True, "allowManualResult": ["FAIL"]}
    service, _ = service_with_store(prepared(data))
    c = client_for(service)
    assert c.get("/api/monitor/ps/PS-03").json()["review"]["allowManualResult"] == ["PASS", "REVIEW"]
    assert c.post(REVIEW.format("PS-03"), json={"status": "FAIL"}).status_code == 422      # no longer allowed
    assert c.post(REVIEW.format("PS-01"), json={"status": "FAIL"}).status_code == 200      # now reviewed by the user


# --- TEST 02-06: save, read back, refresh ------------------------------------------------------------
@pytest.mark.parametrize("chosen", ["PASS", "FAIL", "REVIEW"])
def test_02_03_04_05_a_choice_is_saved_and_read_back(data, chosen):
    service, adapter = service_with_store(prepared(data))
    c = client_for(service)
    r = c.post(REVIEW.format("PS-03"), json={"status": chosen})
    assert r.status_code == 200
    assert r.json()["review"] == {"allowManualResult": ["PASS", "FAIL", "REVIEW"], "status": chosen,
                                  "recordedBy": RECORDED_BY, "recordedAt": "2026-09-26T05:00:00Z"}
    cid = data["curricula"][0]["_id"]
    assert adapter.docs == [{"curriculumId": cid, "psCode": "PS-03",
                             "review": {"status": chosen, "recordedAt": T1, "recordedBy": RECORDED_BY}}]
    assert c.get("/api/monitor/ps/PS-03").json()["review"]["status"] == chosen
    listed = next(x for x in c.get("/api/monitor").json()["results"] if x["psCode"] == "PS-03")
    assert listed["review"]["status"] == chosen


def test_06_07_a_new_service_over_the_same_store_reads_the_review(data):
    docs = []
    first, _ = service_with_store(prepared(data), docs)
    client_for(first).post(REVIEW.format("PS-03"), json={"status": "PASS"})
    again, _ = service_with_store(data, docs)                                    # refresh / restart
    assert client_for(again).get("/api/monitor/ps/PS-03").json()["review"]["status"] == "PASS"


# --- TEST 08 / 18: saving again updates the same record ---------------------------------------------------
def test_08_saving_again_updates_the_one_record_with_the_server_time(data):
    service, adapter = service_with_store(prepared(data))
    c = client_for(service)
    for chosen in ("REVIEW", "PASS", "FAIL"):
        assert c.post(REVIEW.format("PS-03"), json={"status": chosen}).status_code == 200
    assert len(adapter.docs) == 1
    assert adapter.docs[0]["review"] == {"status": "FAIL", "recordedAt": T3, "recordedBy": RECORDED_BY}


def test_the_time_is_the_servers_not_the_callers(data):
    service, adapter = service_with_store(prepared(data))
    client_for(service).post(REVIEW.format("PS-03"), json={"status": "PASS", "recordedAt": "2001-01-01T00:00:00Z"})
    assert adapter.docs[0]["review"]["recordedAt"] == T1


# --- TEST 09-13: rejected requests change nothing ---------------------------------------------------------
@pytest.mark.parametrize("body", [{"status": "N/A"}, {"status": "APPROVED"}, {"status": "VERIFIED"}, {"status": "GOOD"},
                                  {"status": "OK"}, {"status": "pass"}, {"status": ""}, {"status": 1}, {}, None])
def test_09_an_invalid_status_is_422_and_changes_nothing(data, body):
    service, adapter = service_with_store(prepared(data))
    c = client_for(service)
    c.post(REVIEW.format("PS-03"), json={"status": "PASS"})
    before = copy.deepcopy(adapter.docs)
    r = c.post(REVIEW.format("PS-03"), json=body) if body is not None else c.post(REVIEW.format("PS-03"))
    assert r.status_code == 422
    assert adapter.docs == before and c.get("/api/monitor/ps/PS-03").json()["review"]["status"] == "PASS"


@pytest.mark.parametrize("code", [c for c in CODES if c not in REVIEWED])
def test_10_a_ps_without_user_review_cannot_take_one(data, code):
    service, adapter = service_with_store(prepared(data))
    r = client_for(service).post(REVIEW.format(code), json={"status": "PASS"})
    assert r.status_code == 400 and r.json() == {"detail": f"{code} takes no review by the user in its configuration"}
    assert adapter.docs == [] and "set_review" not in adapter.calls


def test_11_unknown_or_inactive_ps_or_no_curriculum_is_404(data):
    data["ps_requirements"][2]["active"] = False                          # PS-03 inactive
    service, adapter = service_with_store(prepared(data))
    c = client_for(service)
    for path in (REVIEW.format("PS-99"), REVIEW.format("PS-03"), REVIEW.format("PS-03") + "?curriculumCode=NONE"):
        assert c.post(path, json={"status": "PASS"}).status_code == 404
    assert adapter.docs == []


def test_11_a_curriculum_that_is_not_there_is_404(data):
    service, adapter = service_with_store(prepared(data))
    r = client_for(service).post(REVIEW.format("PS-03") + "?curriculumCode=NONE", json={"status": "PASS"})
    assert r.status_code == 404 and r.json() == {"detail": "No monitoring result"} and adapter.docs == []


def test_12_several_curricula_without_a_code_is_409(data):
    other = copy.deepcopy(data["curricula"][0])
    other.update(_id=oid(), curriculumCode="OTHER")
    data["curricula"].append(other)
    service, adapter = service_with_store(prepared(data))
    c = client_for(service)
    assert c.post(REVIEW.format("PS-03"), json={"status": "PASS"}).status_code == 409 and adapter.docs == []
    assert c.post(REVIEW.format("PS-03") + "?curriculumCode=OTHER", json={"status": "FAIL"}).status_code == 200
    assert [(d["curriculumId"], d["psCode"]) for d in adapter.docs] == [(other["_id"], "PS-03")]
    first = data["curricula"][0]["curriculumCode"]
    assert c.get(f"/api/monitor/ps/PS-03?curriculumCode={first}").json()["review"]["status"] is None


def test_13_store_unavailable_is_503(data):
    service, _ = service_with_store(prepared(data), fail=True)
    r = client_for(service).post(REVIEW.format("PS-03"), json={"status": "PASS"})
    assert r.status_code == 503 and r.json() == {"detail": "Unable to save the review"} and "FAIL" not in r.text


def test_13_no_store_is_503(data):
    r = client_for(make_service(prepared(data))[0]).post(REVIEW.format("PS-03"), json={"status": "PASS"})
    assert r.status_code == 503


def test_get_cannot_review(data):
    service, adapter = service_with_store(prepared(data))
    assert client_for(service).get(REVIEW.format("PS-03")).status_code == 405 and adapter.docs == []


# --- TEST 14: verification and review share the record and never erase each other -------------------------
def test_14_verification_and_review_live_in_one_record(data):
    service, adapter = service_with_store(prepared(data))
    c = client_for(service)
    c.post(VERIFY.format("PS-03"))
    c.post(REVIEW.format("PS-03"), json={"status": "PASS"})
    c.post(VERIFY.format("PS-03"))
    c.post(REVIEW.format("PS-03"), json={"status": "FAIL"})
    assert len(adapter.docs) == 1
    assert adapter.docs[0]["verification"] == {"verified": True, "verifiedAt": T1}
    assert adapter.docs[0]["review"]["status"] == "FAIL"
    body = c.get("/api/monitor/ps/PS-03").json()
    assert (body["verification"]["verified"], body["review"]["status"]) == (True, "FAIL")


# --- TEST 15-18 and cases A-E: the review changes no result or evidence ----------------------------------------
# Readiness (project owner 2026-09-27, replacing "no readiness reads it" of 2026-09-26): both readinesses count the
# saved review instead of the engine's status; the engine's status itself stays as it was.
@pytest.mark.parametrize("chosen, readiness, generation", [
    ("PASS", {"percentage": 88.89, "passCount": 8, "totalPS": 9}, (Readiness.READY, [])),
    ("FAIL", {"percentage": 77.78, "passCount": 7, "totalPS": 9}, (Readiness.NOT_READY, [("PS-03", Status.FAIL)])),
    ("REVIEW", {"percentage": 77.78, "passCount": 7, "totalPS": 9}, (Readiness.NOT_READY, [("PS-03", Status.REVIEW)])),
])
def test_15_16_17_18_a_review_changes_nothing_but_the_review_and_readiness(data, chosen, readiness, generation):
    service, _ = service_with_store(prepared(data))
    service.review("PS-06", "PASS")                 # PS-06 confirmed by the user: PS-03 is the only PS left to review
    before_data = copy.deepcopy(data)
    before = service.monitor()
    assert before.programme_readiness.model_dump(by_alias=True) == {"percentage": 77.78, "passCount": 7, "totalPS": 9}
    service.review("PS-03", chosen)
    after = service.monitor()
    ignore = {"results": {"__all__": {"review"}}, "programme_readiness": True, "generation_readiness": True}
    assert after.model_dump(exclude=ignore) == before.model_dump(exclude=ignore)      # status, evidence, trace ...
    ps03 = next(r for r in after.results if r.ps_code == "PS-03")
    assert ps03.status is Status.REVIEW and ps03.review.status is Status(chosen)       # engine vs user review
    assert not [s for s in ps03.data_summary if s.label == "Manual result"]            # never fed to the engine
    assert after.programme_readiness.model_dump(by_alias=True) == readiness
    assert (after.generation_readiness.status, [(b.ps_code, b.status) for b in after.generation_readiness.blocking_ps]) \
        == generation
    assert data == before_data                                                        # source / configuration


@pytest.mark.parametrize("engine, chosen", [
    ("REVIEW", "PASS"), ("REVIEW", "FAIL"), ("REVIEW", "REVIEW"),   # cases A, B, C: the configuration as it is
    ("PASS", "PASS"), ("FAIL", "PASS"),                              # cases D, E: the engine status mapped otherwise
])
def test_cases_a_to_e_engine_status_and_review_stay_apart(data, engine, chosen):
    cfg(data, "PS-03")["result"]["review"] = engine          # what the engine gives PS-03 while it waits for review
    service, _ = service_with_store(prepared(data))
    before = next(r for r in service.monitor().results if r.ps_code == "PS-03")
    after = service.review("PS-03", chosen)
    assert before.status is after.status is Status(engine)
    assert after.review.status is Status(chosen)
