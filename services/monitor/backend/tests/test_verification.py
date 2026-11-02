"""Verification (SET 4, project owner 2026-09-26).

The user verifies the evidence shown with a PS result (C). The verification is kept in the Monitor-owned
collection `monitoring_results`, one record per curriculumId + psCode:
{curriculumId, psCode, verification: {verified: true, verifiedAt}}. POST records it (idempotent: the first
verification stands); GET reads it. `approved` stays null. Nothing else of a result changes, nor any
readiness, and Source Data / Configuration are never written.
"""
import copy
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_service
from app.main import create_app
from app.models.status import Status
from app.repositories.monitoring_results import MonitoringResultRepository
from tests.support.fixtures import GENERATION_READINESS, base_data, make_service, oid
from tests.support.memory_store import InMemoryMonitoringResultAdapter

CODES = [f"PS-0{n}" for n in range(1, 10)]
T1 = datetime(2026, 9, 26, 5, 0, tzinfo=timezone.utc)
T2 = datetime(2026, 9, 26, 6, 0, tzinfo=timezone.utc)
ROUTE = "/api/monitor/ps/{}/verification"


class Clock:
    def __init__(self, *times):
        self.times = list(times)

    def __call__(self):
        return self.times.pop(0) if len(self.times) > 1 else self.times[0]


def prepared(data):
    """The collection and data as SET 1-3 left them: generation readiness config and one curriculum document."""
    data["ps_requirements"].append(copy.deepcopy(GENERATION_READINESS))
    data["documents"] = [{"_id": oid(), "documentType": "curriculum", "fileType": "pdf", "fileName": "TEST-1.pdf",
                          "curriculumId": data["curricula"][0]["_id"],
                          "originalFile": {"storage": "local", "path": "test-data/documents/original/TEST-1.pdf"}}]
    return data


def service_with_store(data, docs=None, clock=None, fail=False):
    adapter = InMemoryMonitoringResultAdapter(docs, fail)
    service, source = make_service(data, results=MonitoringResultRepository(adapter, clock or Clock(T1, T2, T2)))
    return service, adapter


def client_for(service):
    app = create_app()
    app.dependency_overrides[get_service] = lambda: service
    return TestClient(app)


def verification(body):
    return body["verification"]


# --- TEST 01: initial state ---------------------------------------------------------------------------
def test_01_before_any_verify_every_ps_reads_not_verified(data):
    service, adapter = service_with_store(prepared(data))
    c = client_for(service)
    for r in c.get("/api/monitor").json()["results"]:
        v = verification(r)
        assert (v["verified"], v["approved"], v["verifiedAt"]) == (False, None, None) and v["found"] >= 0
    assert verification(c.get("/api/monitor/ps/PS-01").json())["verified"] is False
    assert set(adapter.calls) == {"read"}                               # GET never writes


def test_without_a_monitor_owned_store_verification_stays_unknown(data):
    body = client_for(make_service(prepared(data))[0]).get("/api/monitor/ps/PS-01").json()
    assert (verification(body)["verified"], verification(body)["verifiedAt"]) == (None, None)


# --- TEST 03 / 04 / 12: POST, read back, refresh ----------------------------------------------------------
def test_03_04_verify_is_recorded_and_read_back(data):
    service, adapter = service_with_store(prepared(data))
    c = client_for(service)
    r = c.post(ROUTE.format("PS-01"))
    assert r.status_code == 200 and r.json()["psCode"] == "PS-01"
    assert verification(r.json()) == {"found": verification(r.json())["found"], "verified": True, "approved": None,
                                      "verifiedAt": "2026-09-26T05:00:00Z"}
    cid = data["curricula"][0]["_id"]
    assert adapter.docs == [{"curriculumId": cid, "psCode": "PS-01", "verification": {"verified": True, "verifiedAt": T1}}]
    assert verification(c.get("/api/monitor/ps/PS-01").json())["verified"] is True
    listed = {x["psCode"]: verification(x)["verified"] for x in c.get("/api/monitor").json()["results"]}
    assert listed == {code: code == "PS-01" for code in CODES}


def test_12_refresh_reads_the_state_from_the_store(data):
    """A new service over the same stored records (a reload or a restart) still reads PS-01 as verified."""
    docs = []
    first, _ = service_with_store(prepared(data), docs)
    client_for(first).post(ROUTE.format("PS-01"))
    again, _ = service_with_store(data, docs)
    body = client_for(again).get("/api/monitor/ps/PS-01").json()
    assert (verification(body)["verified"], verification(body)["verifiedAt"]) == (True, "2026-09-26T05:00:00Z")


def test_06_verifying_again_creates_no_duplicate_and_keeps_the_first_time(data):
    service, adapter = service_with_store(prepared(data))
    c = client_for(service)
    for _ in range(3):
        assert c.post(ROUTE.format("PS-01")).status_code == 200
    assert len(adapter.docs) == 1 and adapter.docs[0]["verification"]["verifiedAt"] == T1


def test_the_key_is_curriculum_and_ps(data):
    other = copy.deepcopy(data["curricula"][0])
    other.update(_id=oid(), curriculumCode="OTHER")
    data["curricula"].append(other)
    service, adapter = service_with_store(prepared(data))
    c = client_for(service)
    assert c.post(ROUTE.format("PS-01") + "?curriculumCode=OTHER").status_code == 200
    assert [(d["curriculumId"], d["psCode"]) for d in adapter.docs] == [(other["_id"], "PS-01")]
    first = data["curricula"][0]["curriculumCode"]
    assert verification(c.get(f"/api/monitor/ps/PS-01?curriculumCode={first}").json())["verified"] is False
    assert verification(c.get("/api/monitor/ps/PS-01?curriculumCode=OTHER").json())["verified"] is True
    assert verification(c.get("/api/monitor/ps/PS-02?curriculumCode=OTHER").json())["verified"] is False


# --- rejected requests write nothing ------------------------------------------------------------------------
def test_unknown_or_inactive_ps_or_no_curriculum_is_404_and_writes_nothing(data):
    data["ps_requirements"][2]["active"] = False                        # PS-03 inactive
    service, adapter = service_with_store(prepared(data))
    c = client_for(service)
    for path in (ROUTE.format("PS-99"), ROUTE.format("PS-03"), ROUTE.format("PS-01") + "?curriculumCode=NONE"):
        r = c.post(path)
        assert r.status_code == 404 and r.json() == {"detail": "No monitoring result"}
    assert adapter.docs == [] and "set_verified" not in adapter.calls


def test_several_curricula_without_a_code_is_409_and_writes_nothing(data):
    other = copy.deepcopy(data["curricula"][0])
    other.update(_id=oid(), curriculumCode="OTHER")
    data["curricula"].append(other)
    service, adapter = service_with_store(prepared(data))
    assert client_for(service).post(ROUTE.format("PS-01")).status_code == 409 and adapter.docs == []


def test_05_store_failure_is_503_and_nothing_is_verified(data):
    service, _ = service_with_store(prepared(data), fail=True)
    c = client_for(service)
    r = c.post(ROUTE.format("PS-01"))
    assert r.status_code == 503 and r.json() == {"detail": "Unable to save the verification"} and "FAIL" not in r.text
    assert c.get("/api/monitor/ps/PS-01").status_code == 503


def test_without_a_store_verify_is_503(data):
    r = client_for(make_service(prepared(data))[0]).post(ROUTE.format("PS-01"))
    assert r.status_code == 503 and r.json() == {"detail": "Unable to save the verification"}


def test_get_cannot_verify(data):
    service, adapter = service_with_store(prepared(data))
    assert client_for(service).get(ROUTE.format("PS-01")).status_code == 405 and adapter.docs == []


# --- TEST 07 - 11: verifying changes no result, readiness, evidence, source or configuration --------------------
def test_07_to_11_verify_changes_nothing_but_the_verification(data):
    service, _ = service_with_store(prepared(data))
    before_data = copy.deepcopy(data)
    before = service.monitor()
    for code in CODES:
        service.verify(code)
    after = service.monitor()
    ignore = {"results": {"__all__": {"verification": {"verified", "verified_at"}}}}
    assert after.model_dump(exclude=ignore) == before.model_dump(exclude=ignore)          # status, evidence, trace
    assert after.programme_readiness == before.programme_readiness                      # TEST 08
    assert after.generation_readiness == before.generation_readiness                    # TEST 09
    ps03 = next(r for r in after.results if r.ps_code == "PS-03")                       # TEST 10: still user review
    assert (ps03.status, ps03.review_by_user) == (Status.REVIEW, True)
    assert all(r.verification.verified is True and r.verification.approved is None for r in after.results)
    assert data == before_data                                                           # no source / config write


def test_evidence_is_the_same_before_and_after_verify(data):
    service, _ = service_with_store(prepared(data))
    before = service.ps_detail("PS-01").evidence
    after = service.verify("PS-01").evidence
    assert [e.model_dump() for e in after] == [e.model_dump() for e in before] and len(after) == 1


def test_a_record_that_is_not_a_verification_reads_as_not_verified(data):
    cid = data["curricula"][0]["_id"]
    docs = [{"curriculumId": cid, "psCode": "PS-01"},                                        # no verification
            {"curriculumId": cid, "psCode": "PS-02", "verification": {"verified": "yes"}},     # not true
            {"curriculumId": cid, "psCode": "PS-04", "verification": {"verified": True,
                                                                      "verifiedAt": datetime(2026, 9, 26, 5, 0)}}]
    service, _ = service_with_store(prepared(data), docs)
    got = {r.ps_code: (r.verification.verified, r.verification.verified_at) for r in service.monitor().results}
    assert got["PS-01"] == got["PS-02"] == (False, None)
    assert got["PS-04"] == (True, T1)                                  # MongoDB's zone-less UTC read as UTC
