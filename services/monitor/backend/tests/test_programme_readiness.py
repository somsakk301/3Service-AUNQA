"""Programme Readiness (project owner, 2026-09-26): PASS count / 9 x 100, rounded to 2 decimals.

Only PASS counts; FAIL, REVIEW, N/A and a PS without a result do not; the denominator is always 9.
It is aggregated from the results the engine produced and is separate from generation readiness.
"""
import copy

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_service
from app.main import create_app
from app.models.schemas import (
    CurriculumInfo, GenerationReadiness, MonitorResponse, ProgrammeReadiness, PSResult, Verification,
)
from app.models.status import Readiness, Status
from app.services import generation_readiness
from tests.support.fixtures import AUTHORITATIVE_CONFIG, GENERATION_READINESS, ManualResults, make_service

CODES = [f"PS-0{n}" for n in range(1, 10)]
P, F, R, NA, MISSING = "PASS", "FAIL", "REVIEW", "N/A", None


def result(code, status):
    """A PS result as the engine returns it; only psCode and status matter to the aggregation."""
    return PSResult(ps_code=code, status=Status(status), checks=[], data_summary=[], data_found=[],
                    verification=Verification(), missing_information=[], evidence=[], traceability=[],
                    data_completeness="complete")


def results_for(statuses):
    return [result(c, s) for c, s in zip(CODES, statuses) if s is not MISSING]


def response(results, readiness=None):
    return MonitorResponse(curriculum=CurriculumInfo(curriculum_code="C"), data_completeness="complete",
                           results=results, generation_readiness=readiness or GenerationReadiness())


def programme(resp):
    return resp.model_dump(by_alias=True)["programmeReadiness"]


# statuses of PS-01 ... PS-09 (None = no result), expected passCount, expected percentage
SCENARIOS = {
    "TEST 01: 9 PASS": ([P] * 9, 9, 100),
    "TEST 02: 8 PASS, 1 FAIL": ([P] * 8 + [F], 8, 88.89),
    "TEST 03: 7 PASS, 1 FAIL, 1 REVIEW": ([P] * 7 + [F, R], 7, 77.78),
    "TEST 04: 7 PASS, 2 N/A": ([P] * 7 + [NA, NA], 7, 77.78),
    "TEST 05: 6 PASS, 1 FAIL, 1 REVIEW, 1 N/A": ([P] * 6 + [F, R, NA], 6, 66.67),
    "TEST 06: 5 PASS, 2 FAIL, 2 REVIEW": ([P] * 5 + [F, F, R, R], 5, 55.56),
    "TEST 07: 0 PASS": ([F, F, F, R, R, R, NA, NA, NA], 0, 0),
    "TEST 08: 4 PASS, 2 FAIL, 1 REVIEW, 2 missing": ([P] * 4 + [F, F, R, MISSING, MISSING], 4, 44.44),
    "owner example: PS-08, PS-09 without result": ([P, P, F, P, R, P, P, MISSING, MISSING], 5, 55.56),
}


@pytest.mark.parametrize("case", list(SCENARIOS))
def test_programme_readiness_scenarios(case):
    statuses, passed, percentage = SCENARIOS[case]
    assert programme(response(results_for(statuses))) == {"percentage": percentage, "passCount": passed, "totalPS": 9}


@pytest.mark.parametrize("passed, percentage", [(0, 0), (1, 11.11), (2, 22.22), (3, 33.33), (4, 44.44), (5, 55.56),
                                                (6, 66.67), (7, 77.78), (8, 88.89), (9, 100)])
def test_percentage_is_rounded_to_two_decimals_after_counting(passed, percentage):
    r = ProgrammeReadiness.of(results_for([P] * passed + [F] * (9 - passed)))
    assert (r.pass_count, r.percentage, r.total_ps) == (passed, percentage, 9)


def test_10_not_applicable_is_not_pass():
    assert ProgrammeReadiness.of(results_for([NA] * 9)).pass_count == 0
    assert ProgrammeReadiness.of(results_for([P] * 8 + [NA])).percentage == 88.89


def test_11_denominator_stays_nine_whatever_the_number_of_results():
    for n in range(10):                                   # 0 ... 9 results, every one PASS
        r = ProgrammeReadiness.of(results_for([P] * n + [MISSING] * (9 - n)))
        assert (r.pass_count, r.total_ps, r.percentage) == (n, 9, round(n * 100 / 9, 2))


def test_a_ps_counts_once_even_if_returned_twice():
    rs = results_for([P] * 7 + [F, F]) + [result("PS-01", P)]
    assert ProgrammeReadiness.of(rs).pass_count == 7


def test_the_aggregation_changes_no_result():
    rs = results_for([P, F, R, NA, P, P, P, MISSING, P])
    before = [r.model_dump() for r in rs]
    programme(response(rs))
    assert [r.model_dump() for r in rs] == before


# --- over real evaluation results -------------------------------------------------------------------
def monitor(data, **kw):
    service, _ = make_service(data, **kw)
    return service.monitor()


def test_09_ps03_without_user_review_is_not_pass(data):
    resp = monitor(data)
    statuses = {r.ps_code: r.status for r in resp.results}
    assert statuses["PS-03"] is Status.REVIEW and statuses["PS-08"] is Status.NA   # user review; no special instructor
    assert statuses["PS-06"] is Status.REVIEW                                          # user confirmation, none yet
    assert resp.programme_readiness.model_dump(by_alias=True) == {"percentage": 66.67, "passCount": 6, "totalPS": 9}


def test_ps03_counts_only_with_the_result_the_reviewer_chose(data):
    resp = monitor(data, manual=ManualResults({"PS-03": "PASS"}))
    assert (resp.programme_readiness.pass_count, resp.programme_readiness.percentage) == (7, 77.78)   # PS-06 still REVIEW


def test_engine_results_fail_review_and_na(data):
    data["appointments"].remove(next(a for a in data["appointments"] if a["role"] == "programmeResponsible"))
    resp = monitor(data)
    assert sorted(r.status.value for r in resp.results) == sorted([P] * 5 + [F, R, R, NA])   # PS-03, PS-06: REVIEW
    assert (resp.programme_readiness.pass_count, resp.programme_readiness.percentage) == (5, 55.56)


def test_11_inactive_configurations_do_not_shrink_the_denominator(data):
    for d in data["ps_requirements"]:
        if d["psCode"] in ("PS-05", "PS-06"):
            d["active"] = False
    resp = monitor(data)
    assert len(resp.results) == 7
    assert resp.programme_readiness.model_dump(by_alias=True) == {"percentage": 55.56, "passCount": 5, "totalPS": 9}


def test_no_curriculum_gives_no_programme_readiness():
    resp = monitor({"ps_requirements": copy.deepcopy(AUTHORITATIVE_CONFIG)})
    assert resp.curriculum is None and resp.results == [] and resp.programme_readiness is None


# --- API --------------------------------------------------------------------------------------------
def client_for(service):
    app = create_app()
    app.dependency_overrides[get_service] = lambda: service
    return TestClient(app)


def test_12_api_response_schema(data):
    data["ps_requirements"].append(copy.deepcopy(GENERATION_READINESS))
    body = client_for(make_service(data)[0]).get("/api/monitor").json()
    assert body["programmeReadiness"] == {"percentage": 66.67, "passCount": 6, "totalPS": 9}
    assert body["generationReadiness"]["status"] == "NOT_READY"                     # a separate object
    assert set(body["programmeReadiness"]) & set(body["generationReadiness"]) == set()
    assert body["overallStatus"] is None                                             # unchanged
    assert {"curriculum", "overallStatus", "dataCompleteness", "results", "generationReadiness",
            "programmeReadiness"} == set(body)


def test_12_openapi_declares_programme_readiness():
    schemas = create_app().openapi()["components"]["schemas"]
    assert "programmeReadiness" in schemas["MonitorResponse"]["properties"]
    assert schemas["ProgrammeReadiness"]["required"] == ["percentage", "passCount", "totalPS"]


def test_api_ps_detail_has_no_programme_readiness(data):
    body = client_for(make_service(data)[0]).get("/api/monitor/ps/PS-01").json()
    assert "programmeReadiness" not in body


def test_api_no_curriculum_keeps_its_empty_response():
    body = client_for(make_service({})[0]).get("/api/monitor").json()
    assert body["curriculum"] is None and body["results"] == [] and body["programmeReadiness"] is None


# --- TEST 15: separate from generation readiness ------------------------------------------------------
def test_15_owner_example_is_77_78_percent_and_ready():
    rs = results_for([P] * 7 + [NA, NA])
    gr = generation_readiness.decide([copy.deepcopy(GENERATION_READINESS)], AUTHORITATIVE_CONFIG, rs)
    resp = response(rs, gr)
    assert resp.generation_readiness.status is Readiness.READY
    assert programme(resp) == {"percentage": 77.78, "passCount": 7, "totalPS": 9}


def test_15_generation_readiness_is_unchanged_by_programme_readiness(data):
    data["ps_requirements"].append(copy.deepcopy(GENERATION_READINESS))
    gr = monitor(data).generation_readiness
    assert (gr.status, [(b.ps_code, b.status) for b in gr.blocking_ps], gr.issue, gr.detail) == \
        (Readiness.NOT_READY, [("PS-03", Status.REVIEW), ("PS-06", Status.REVIEW)], None, None)
