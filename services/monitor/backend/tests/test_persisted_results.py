"""Persistent Monitoring Result (SET 6, project owner 2026-09-26).

`POST /api/monitor/results` evaluates now, exactly as GET does, then keeps each PS's engine status in the
Monitor-owned `monitoring_results` record of curriculumId + psCode: `result: {status, evaluatedAt}` (server time).
Current state: the last save replaces the one before (no history), and it stays as saved when source data change.
GET reads it back as `persistedResult` and never writes. Nothing stored is fed back to the engine; readiness,
evidence and traceability are not kept, and verification / review in the same record stay as they are.
"""
import copy
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user, get_service
from app.main import create_app
from app.models.auth import AuthenticatedUser
from app.models.status import Status
from app.repositories.base import DataSourceError
from app.repositories.configuration import ConfigurationRepository
from app.repositories.monitoring_results import MonitoringResultRepository
from app.repositories.source_data import SourceDataRepository
from app.services.monitoring_service import MonitoringService
from tests.support.fixtures import GENERATION_READINESS, FixedReferences, TEST_CLOCK_YEAR, make_service, oid
from tests.support.memory_store import InMemoryConfigurationAdapter, InMemoryMonitoringResultAdapter, InMemorySourceAdapter

T1 = datetime(2026, 9, 26, 5, 0, tzinfo=timezone.utc)
T2 = datetime(2026, 9, 26, 6, 0, tzinfo=timezone.utc)
T3 = datetime(2026, 9, 26, 7, 0, tzinfo=timezone.utc)
SAVE = "/api/monitor/results"
CODES = [f"PS-0{n}" for n in range(1, 10)]
TEST_USER = AuthenticatedUser(user_id="507f1f77bcf86cd799439011", name="ผู้ตรวจทดสอบ")


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
    service, source = make_service(data, results=MonitoringResultRepository(adapter, clock or Clock(T1, T2, T3)))
    return service, adapter


def client_for(service):
    app = create_app()
    app.dependency_overrides[get_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: TEST_USER
    return TestClient(app)


def persisted(body):
    return {r["psCode"]: r["persistedResult"] for r in body["results"]}


# --- TEST 01 / 02 / 05: save, read back, same as the current evaluation -----------------------------------------
def test_01_02_05_saving_keeps_every_ps_status_the_engine_gives_now(data):
    service, adapter = service_with_store(prepared(data))
    c = client_for(service)
    current = c.get("/api/monitor").json()
    assert set(persisted(current).values()) == {None}                     # nothing saved yet
    r = c.post(SAVE)
    assert r.status_code == 200
    expected = {x["psCode"]: {"status": x["status"], "evaluatedAt": "2026-09-26T05:00:00Z"} for x in current["results"]}
    assert persisted(r.json()) == expected
    assert persisted(c.get("/api/monitor").json()) == expected            # GET reads it back
    cid = data["curricula"][0]["_id"]
    assert sorted((d["curriculumId"], d["psCode"], d["result"]["status"]) for d in adapter.docs) == \
        sorted((cid, x["psCode"], x["status"]) for x in current["results"])
    assert all(d["result"]["evaluatedAt"] == T1 for d in adapter.docs) and len(adapter.docs) == 9
    assert c.get("/api/monitor/ps/PS-05").json()["persistedResult"] == expected["PS-05"]


def test_03_04_a_new_service_over_the_same_store_reads_the_saved_result(data):
    docs = []
    first, _ = service_with_store(prepared(data), docs)
    saved = persisted(client_for(first).post(SAVE).json())
    again, _ = service_with_store(data, docs)                                        # refresh / restart
    assert persisted(client_for(again).get("/api/monitor").json()) == saved


# --- TEST 06 / 07 / 10: readiness, evidence and the result are unchanged by saving ----------------------------------
def test_06_07_10_saving_changes_nothing_but_the_persisted_result(data):
    service, _ = service_with_store(prepared(data))
    before_data = copy.deepcopy(data)
    before = service.monitor()
    service.save_results()
    after = service.monitor()
    ignore = {"results": {"__all__": {"persisted_result"}}}
    assert after.model_dump(exclude=ignore) == before.model_dump(exclude=ignore)       # status, evidence, trace ...
    assert after.programme_readiness == before.programme_readiness
    assert after.generation_readiness == before.generation_readiness
    assert data == before_data                                                        # TEST 12 / 13


# --- TEST 08 / 09: verification and review in the same record stay ---------------------------------------------
def test_08_09_verification_and_review_survive_a_save_and_a_save_survives_them(data):
    service, adapter = service_with_store(prepared(data))
    c = client_for(service)
    c.post("/api/monitor/ps/PS-03/verification")
    c.post("/api/monitor/ps/PS-03/review", json={"status": "PASS"})
    c.post(SAVE)
    c.post("/api/monitor/ps/PS-03/review", json={"status": "FAIL"})
    ps03 = next(d for d in adapter.docs if d["psCode"] == "PS-03")
    assert set(ps03) == {"curriculumId", "psCode", "verification", "review", "result"}
    assert ps03["verification"] == {"verified": True, "verifiedAt": T1}
    assert ps03["review"]["status"] == "FAIL" and ps03["result"]["status"] == "REVIEW"   # engine status, not the review
    body = c.get("/api/monitor/ps/PS-03").json()
    assert (body["status"], body["review"]["status"], body["persistedResult"]["status"], body["verification"]["verified"]) \
        == ("REVIEW", "FAIL", "REVIEW", True)


# --- TEST 11: current state, no duplicate ------------------------------------------------------------------------
def test_11_saving_again_replaces_the_result_in_the_same_records(data):
    service, adapter = service_with_store(prepared(data))
    c = client_for(service)
    for _ in range(3):
        assert c.post(SAVE).status_code == 200
    assert len(adapter.docs) == 9 and {d["result"]["evaluatedAt"] for d in adapter.docs} == {T3}


def test_the_saved_result_stays_as_saved_when_source_data_change(data):
    service, _ = service_with_store(prepared(data))
    service.save_results()
    data["appointments"].remove(next(a for a in data["appointments"] if a["role"] == "programmeResponsible"))
    ps01 = next(r for r in service.monitor().results if r.ps_code == "PS-01")
    assert (ps01.status, ps01.persisted_result.status) == (Status.FAIL, Status.PASS)   # current vs saved
    service.save_results()
    ps01 = next(r for r in service.monitor().results if r.ps_code == "PS-01")
    assert (ps01.status, ps01.persisted_result.status) == (Status.FAIL, Status.FAIL)


def test_a_stored_result_is_never_fed_back_to_the_engine(data):
    cid = data["curricula"][0]["_id"]
    docs = [{"curriculumId": cid, "psCode": code, "result": {"status": "FAIL", "evaluatedAt": T1}} for code in CODES]
    service, _ = service_with_store(prepared(data), docs)
    plain = make_service(copy.deepcopy(data))[0].monitor()
    got = service.monitor()
    assert [r.status for r in got.results] == [r.status for r in plain.results]
    assert got.programme_readiness == plain.programme_readiness
    assert got.generation_readiness == plain.generation_readiness
    assert {r.persisted_result.status for r in got.results} == {Status.FAIL}


def test_curricula_are_kept_apart_and_inactive_ps_are_not_saved(data):
    other = copy.deepcopy(data["curricula"][0])
    other.update(_id=oid(), curriculumCode="OTHER")
    data["curricula"].append(other)
    data["ps_requirements"][4]["active"] = False                                  # PS-05
    service, adapter = service_with_store(prepared(data))
    c = client_for(service)
    assert c.post(SAVE + "?curriculumCode=OTHER").status_code == 200
    assert {d["curriculumId"] for d in adapter.docs} == {other["_id"]}
    assert sorted(d["psCode"] for d in adapter.docs) == [c_ for c_ in CODES if c_ != "PS-05"]
    first = data["curricula"][0]["curriculumCode"]
    assert set(persisted(c.get(f"/api/monitor?curriculumCode={first}").json()).values()) == {None}


# --- GET never writes; rejected saves write nothing ---------------------------------------------------------------
def test_get_never_writes(data):
    service, adapter = service_with_store(prepared(data))
    c = client_for(service)
    for path in ("/api/monitor", "/api/monitor/ps/PS-01"):
        c.get(path)
    assert set(adapter.calls) == {"read"} and adapter.docs == []
    assert c.get(SAVE).status_code == 405


def test_no_curriculum_is_404_and_several_without_a_code_is_409(data):
    service, adapter = service_with_store(prepared(data))
    assert client_for(service).post(SAVE + "?curriculumCode=NONE").status_code == 404
    other = copy.deepcopy(data["curricula"][0])
    other.update(_id=oid(), curriculumCode="OTHER")
    data["curricula"].append(other)
    assert client_for(service).post(SAVE).status_code == 409
    assert adapter.docs == []


def test_14_store_unavailable_is_503_and_nothing_is_written(data):
    service, adapter = service_with_store(prepared(data), fail=True)
    r = client_for(service).post(SAVE)
    assert r.status_code == 503 and r.json() == {"detail": "Unable to save the monitoring result"} and "FAIL" not in r.text
    assert adapter.docs == []


def test_14_source_unavailable_is_503_and_nothing_is_written(data):
    class DocumentsUnreadable(InMemorySourceAdapter):
        def find(self, collection, query):
            if collection == "documents":                                   # fails in the middle of the evaluation
                raise DataSourceError("connection refused")
            return super().find(collection, query)

    adapter = InMemoryMonitoringResultAdapter()
    service = MonitoringService(ConfigurationRepository(InMemoryConfigurationAdapter(prepared(data)["ps_requirements"])),
                                SourceDataRepository(DocumentsUnreadable(data)), FixedReferences({"currentYear": TEST_CLOCK_YEAR}),
                                results=MonitoringResultRepository(adapter))
    assert client_for(service).post(SAVE).status_code == 503
    assert adapter.docs == [] and "set_results" not in adapter.calls


def test_no_store_is_503(data):
    assert client_for(make_service(prepared(data))[0]).post(SAVE).status_code == 503


@pytest.mark.parametrize("code", CODES)
def test_ps_detail_shows_the_saved_result_of_that_ps(data, code):
    service, _ = service_with_store(prepared(data))
    c = client_for(service)
    listed = persisted(c.post(SAVE).json())[code]
    assert c.get(f"/api/monitor/ps/{code}").json()["persistedResult"] == listed
