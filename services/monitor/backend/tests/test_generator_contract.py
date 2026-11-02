"""Document Generation contract (SET 7, project owner 2026-09-26): pull, readiness only.

The Document Generation side calls `GET /api/monitor?curriculumCode=<code>` and reads `generationReadiness.status`
alone: "READY" or "NOT_READY" as SET 1 decides it (null when the configuration gives no decision). It then reads
what it needs from its own database. Mornitor pushes nothing: no outbound call, webhook or write for the generator.
"""
import copy
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_service
from app.main import create_app
from app.repositories.configuration import ConfigurationRepository
from app.repositories.monitoring_results import MonitoringResultRepository
from app.repositories.source_data import SourceDataRepository
from app.services import generation_readiness
from app.services.monitoring_service import MonitoringService
from tests.support.fixtures import (
    AUTHORITATIVE_CONFIG, GENERATION_READINESS, ManualResults, add_person, appointment, base_data, make_service, oid,
)
from tests.support.memory_store import FailingSourceAdapter, InMemoryConfigurationAdapter, InMemoryMonitoringResultAdapter

APP_DIR = Path(__file__).resolve().parents[1] / "app"
CODES = [f"PS-0{n}" for n in range(1, 10)]


def with_readiness(data):
    data["ps_requirements"].append(copy.deepcopy(GENERATION_READINESS))
    return data


def client_for(service):
    app = create_app()
    app.dependency_overrides[get_service] = lambda: service
    return TestClient(app)


def generator_reads(service, curriculum_code):
    """What the Document Generation side does: GET, then only generationReadiness.status."""
    r = client_for(service).get(f"/api/monitor?curriculumCode={curriculum_code}")
    return r.status_code, (r.json()["generationReadiness"]["status"] if r.status_code == 200 else None)


def code_of(data):
    return data["curricula"][0]["curriculumCode"]


# --- the status the generator reads is SET 1's, over the current evaluation ----------------------------------
def test_not_ready_as_set_1_decides_it(data):
    service, _ = make_service(with_readiness(data))
    assert generator_reads(service, code_of(data)) == (200, "NOT_READY")        # PS-03 is REVIEW (user review)


def test_ready_as_set_1_decides_it(data):
    service, _ = make_service(with_readiness(data), manual=ManualResults(REVIEWS_PASS))   # test double of the port
    assert generator_reads(service, code_of(data)) == (200, "READY")


def test_null_when_the_configuration_gives_no_decision(data):
    service, _ = make_service(data)                                              # no generationReadiness document
    assert generator_reads(service, code_of(data)) == (200, None)


@pytest.mark.parametrize("manual", [None, {"PS-03": "PASS"}])
def test_the_status_is_exactly_the_existing_implementation(data, manual):
    service, _ = make_service(with_readiness(data), manual=ManualResults(manual) if manual else None)
    body = client_for(service).get(f"/api/monitor?curriculumCode={code_of(data)}").json()
    current = service.monitor(code_of(data))
    decided = generation_readiness.decide([GENERATION_READINESS], AUTHORITATIVE_CONFIG, current.results)
    assert body["generationReadiness"] == decided.model_dump(by_alias=True, mode="json")


def test_the_status_comes_from_the_current_evaluation_not_from_saved_results(data):
    """Saved results say every PS PASSed; the generator still reads the readiness of the current evaluation."""
    cid = data["curricula"][0]["_id"]
    saved = [{"curriculumId": cid, "psCode": c, "result": {"status": "PASS", "evaluatedAt": datetime.now(timezone.utc)}}
             for c in CODES]
    service, _ = make_service(with_readiness(data), results=MonitoringResultRepository(InMemoryMonitoringResultAdapter(saved)))
    assert generator_reads(service, code_of(data)) == (200, "NOT_READY")


# --- resume plan A: READY / NOT_READY cases, read over HTTP -----------------------------------------------
REVIEWS_PASS = {"PS-03": "PASS", "PS-06": "PASS"}   # TEST-ONLY double of the manual-result port: no REVIEW blocks


def qualified_special_instructor(data):
    pid = add_person(data, "specialInstructor", degree="master")
    next(p for p in data["persons"] if p["_id"] == pid)["hasTeachingExperience"] = True


def statuses_of(service, code):
    return {r.ps_code: r.status.value for r in service.monitor(code).results}


def test_a1_every_required_ps_pass_is_ready(data):
    qualified_special_instructor(with_readiness(data))
    service, _ = make_service(data, manual=ManualResults(REVIEWS_PASS))
    assert set(statuses_of(service, code_of(data)).values()) == {"PASS"}
    assert generator_reads(service, code_of(data)) == (200, "READY")


def test_a2_not_applicable_is_ready(data):
    service, _ = make_service(with_readiness(data), manual=ManualResults(REVIEWS_PASS))
    assert statuses_of(service, code_of(data))["PS-08"] == "N/A"
    assert generator_reads(service, code_of(data)) == (200, "READY")


def test_a3_one_fail_is_not_ready(data):
    data["appointments"].remove(next(a for a in data["appointments"] if a["role"] == "programmeResponsible"))
    service, _ = make_service(with_readiness(data), manual=ManualResults(REVIEWS_PASS))
    assert [c for c, s in statuses_of(service, code_of(data)).items() if s not in ("PASS", "N/A")] == ["PS-01"]
    assert generator_reads(service, code_of(data)) == (200, "NOT_READY")


def test_a4_one_review_is_not_ready(data):
    service, _ = make_service(with_readiness(data), manual=ManualResults({"PS-06": "PASS"}))
    assert [c for c, s in statuses_of(service, code_of(data)).items() if s not in ("PASS", "N/A")] == ["PS-03"]
    assert generator_reads(service, code_of(data)) == (200, "NOT_READY")


def test_a5_a_required_ps_without_result_is_not_ready(data):
    data["ps_requirements"][4]["active"] = False                     # PS-05: required, no result
    service, _ = make_service(with_readiness(data), manual=ManualResults(REVIEWS_PASS))
    assert "PS-05" not in statuses_of(service, code_of(data))
    assert generator_reads(service, code_of(data)) == (200, "NOT_READY")


def test_a6_only_the_configured_required_ps_count(data):
    with_readiness(data)
    data["ps_requirements"][-1]["generationReadiness"]["requiredPS"].remove("PS-03")   # TEST-ONLY config variant
    service, _ = make_service(data, manual=ManualResults({"PS-06": "PASS"}))         # PS-03 REVIEW, not required
    assert generator_reads(service, code_of(data)) == (200, "READY")


def base_data_for(data):
    """Fresh test data under the same curriculum code."""
    fresh = base_data()
    fresh["curricula"][0]["curriculumCode"] = code_of(data)
    return fresh


def test_programme_readiness_does_not_decide_generation_readiness(data):
    """88.89% with a REVIEW is NOT_READY; 88.89% with an N/A is READY (SET 1 and SET 2 stay apart)."""
    qualified_special_instructor(with_readiness(data))
    service, _ = make_service(data, manual=ManualResults({"PS-06": "PASS"}))        # 8 PASS + PS-03 REVIEW
    body = client_for(service).get(f"/api/monitor?curriculumCode={code_of(data)}").json()
    assert (body["programmeReadiness"]["percentage"], body["generationReadiness"]["status"]) == (88.89, "NOT_READY")
    plain = make_service(with_readiness(copy.deepcopy(base_data_for(data))), manual=ManualResults(REVIEWS_PASS))[0]
    body = client_for(plain).get(f"/api/monitor?curriculumCode={code_of(data)}").json()   # 8 PASS + PS-08 N/A
    assert (body["programmeReadiness"]["percentage"], body["generationReadiness"]["status"]) == (88.89, "READY")


# --- resume plan B: the curriculumCode the generator sends ----------------------------------------------------
def test_each_curriculum_reads_its_own_readiness(data):
    """Curriculum A is ready; curriculum B (4 responsible) is not: neither answer leaks into the other."""
    b_id = oid()
    data["curricula"].append({**copy.deepcopy(data["curricula"][0]), "_id": b_id, "curriculumCode": "B"})
    a_people = [a["personId"] for a in data["appointments"] if a["role"] == "programmeResponsible"]
    for pid in a_people[:4]:
        data["appointments"] += [appointment(b_id, pid, "programmeResponsible"), appointment(b_id, pid, "programmeStaff")]
    service, _ = make_service(with_readiness(data), manual=ManualResults(REVIEWS_PASS))
    assert generator_reads(service, code_of(data)) == (200, "READY")
    assert generator_reads(service, "B") == (200, "NOT_READY")
    assert generator_reads(service, code_of(data)) == (200, "READY")


def test_one_curriculum_needs_no_curriculum_code(data):
    service, _ = make_service(with_readiness(data))
    r = client_for(service).get("/api/monitor")
    assert r.status_code == 200 and r.json()["generationReadiness"]["status"] == "NOT_READY"


# --- status codes the generator meets --------------------------------------------------------------------
def test_an_unknown_curriculum_is_not_ready_with_no_result(data):
    service, _ = make_service(with_readiness(data))
    r = client_for(service).get("/api/monitor?curriculumCode=NO-SUCH-CODE").json()
    assert (r["curriculum"], r["generationReadiness"]["status"]) == (None, "NOT_READY")


def test_several_curricula_need_a_curriculum_code(data):
    other = copy.deepcopy(data["curricula"][0])
    other.update(_id=oid(), curriculumCode="OTHER")
    data["curricula"].append(other)
    service, _ = make_service(with_readiness(data))
    assert client_for(service).get("/api/monitor").status_code == 409
    assert generator_reads(service, "OTHER")[0] == 200


def test_a_database_failure_is_503_never_a_readiness(data):
    service = MonitoringService(ConfigurationRepository(InMemoryConfigurationAdapter(with_readiness(data)["ps_requirements"])),
                                SourceDataRepository(FailingSourceAdapter()))
    r = client_for(service).get(f"/api/monitor?curriculumCode={code_of(data)}")
    assert r.status_code == 503 and "READY" not in r.text


# --- pull only: no side effect, nothing pushed -------------------------------------------------------------
def test_reading_readiness_has_no_side_effect(data):
    adapter = InMemoryMonitoringResultAdapter()
    service, source = make_service(with_readiness(data), results=MonitoringResultRepository(adapter))
    before = copy.deepcopy(data)
    for _ in range(3):
        generator_reads(service, code_of(data))
    assert data == before and {op for op, _ in source.calls} == {"find"}
    assert set(adapter.calls) == {"read"} and adapter.docs == []


def test_the_openapi_contract_declares_the_status():
    schemas = create_app().openapi()["components"]["schemas"]
    assert schemas["GenerationReadiness"]["properties"]["status"] == {
        "anyOf": [{"$ref": "#/components/schemas/Readiness"}, {"type": "null"}]}
    assert schemas["Readiness"]["enum"] == ["READY", "NOT_READY"]
    assert "generationReadiness" in schemas["MonitorResponse"]["properties"]


def test_mornitor_pushes_nothing():
    """No outbound HTTP client, webhook or generator write path in the application (project owner: pull only)."""
    outbound = re.compile(r"^\s*(import|from)\s+(httpx|requests|urllib\.request|urllib3|aiohttp|http\.client)\b", re.M)
    for path in APP_DIR.rglob("*.py"):
        assert not outbound.search(path.read_text()), path
    from app.adapters.external_services import ExternalServiceAAdapter, ExternalServiceBAdapter
    for cls in (ExternalServiceAAdapter, ExternalServiceBAdapter):
        assert {n for n in vars(cls) if not n.startswith("_")} == set()              # still no operation
    paths = create_app().openapi()["paths"]
    assert not [p for p in paths if re.search(r"generat|webhook|push|notify", p, re.I)]
