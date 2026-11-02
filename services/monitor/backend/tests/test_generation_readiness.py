"""Generation readiness configuration (project owner, 2026-09-26).

One document of the existing `ps_requirements` collection, told apart by `configType`, decides READY /
NOT_READY from the PS results: {"configType": "generationReadiness", "generationReadiness": {...}}.
Nothing of it lives in application code, and it never takes part in PS evaluation.
"""
import copy
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.adapters.mongo import CONFIGURATION_COLLECTION, MongoConfigurationAdapter
from app.api.dependencies import get_service
from app.main import create_app
from app.models.status import Readiness, Status
from app.repositories.base import DataSourceError
from app.repositories.configuration import ConfigurationRepository
from app.repositories.source_data import SourceDataRepository
from app.services.generation_readiness import CONFIG_TYPE, ReadinessConfigProblem, validate
from app.services.monitoring_service import MonitoringService
from tests.support.fixtures import (
    AUTHORITATIVE_CONFIG, GENERATION_READINESS, ManualResults, add_person, base_data, make_service,
)
from tests.support.memory_store import InMemoryConfigurationAdapter, InMemorySourceAdapter

APP_DIR = Path(__file__).resolve().parents[1] / "app"
# Expected values: the project owner's file (fixtures/PROVENANCE.md). Test expectations, not application code.
OWNER_REQUIRED_PS = ["PS-01", "PS-02", "PS-03", "PS-04", "PS-05", "PS-06", "PS-07", "PS-08", "PS-09"]


def with_readiness(data, doc=None):
    """The collection as the project owner defined it: the nine PS configurations plus this document."""
    data["ps_requirements"].append(copy.deepcopy(GENERATION_READINESS if doc is None else doc))
    return data


def readiness_body(data):
    return next(d for d in data["ps_requirements"] if d.get("configType") == CONFIG_TYPE)[CONFIG_TYPE]


def monitor(data, **kw):
    service, _ = make_service(data, **kw)
    return service.monitor()


def blocking(resp):
    return [(b.ps_code, b.status) for b in resp.generation_readiness.blocking_ps]


def client_for(service):
    app = create_app()
    app.dependency_overrides[get_service] = lambda: service
    return TestClient(app)


def stored_document(data):
    repo = ConfigurationRepository(InMemoryConfigurationAdapter(data["ps_requirements"]))
    docs = repo.load_by_type(CONFIG_TYPE)
    assert len(docs) == 1
    return docs[0]


# --- the document -------------------------------------------------------------------------------
def test_fixture_is_the_document_shape_the_owner_defined():
    assert set(GENERATION_READINESS) == {"configType", "generationReadiness"}
    assert GENERATION_READINESS["configType"] == "generationReadiness"
    assert "psCode" not in GENERATION_READINESS and "active" not in GENERATION_READINESS
    assert set(GENERATION_READINESS["generationReadiness"]) == {"requiredPS", "readyWhen", "requiredAll"}


# TEST 1
def test_1_generation_readiness_is_read_from_ps_requirements(data):
    with_readiness(data)
    adapter = InMemoryConfigurationAdapter(data["ps_requirements"])
    docs = ConfigurationRepository(adapter).load_by_type(CONFIG_TYPE)
    assert docs == [GENERATION_READINESS] and adapter.calls == ["read_by_type"]


# TEST 2 .. TEST 6: the values the repository returns from the collection
def test_2_required_ps_has_nine_entries(data):
    assert len(stored_document(with_readiness(data))["generationReadiness"]["requiredPS"]) == 9


def test_3_required_ps_lists_ps01_to_ps09(data):
    assert stored_document(with_readiness(data))["generationReadiness"]["requiredPS"] == OWNER_REQUIRED_PS


def test_4_allowed_status_is_pass_and_na(data):
    assert stored_document(with_readiness(data))["generationReadiness"]["readyWhen"]["allowedStatus"] == ["PASS", "N/A"]


def test_5_blocked_status_is_fail_and_review(data):
    assert stored_document(with_readiness(data))["generationReadiness"]["readyWhen"]["blockedStatus"] == ["FAIL", "REVIEW"]


def test_6_required_all_is_true(data):
    assert stored_document(with_readiness(data))["generationReadiness"]["requiredAll"] is True


def test_the_rule_comes_from_the_document(data):
    rule = validate(stored_document(with_readiness(data)))
    assert rule.required == tuple(OWNER_REQUIRED_PS)
    assert rule.allowed == {"PASS", "N/A"} and rule.blocked == {"FAIL", "REVIEW"}


# TEST 7 + isolation: the nine PS configurations load and evaluate exactly as before
def test_7_the_nine_ps_configurations_still_load_unchanged(data):
    with_readiness(data)
    repo = ConfigurationRepository(InMemoryConfigurationAdapter(data["ps_requirements"]))
    assert repo.load_active_requirements() == AUTHORITATIVE_CONFIG
    for doc in AUTHORITATIVE_CONFIG:
        assert repo.get_requirement(doc["psCode"]) == doc


def scenario_base(d): ...


def scenario_fail_and_special_instructor(d):
    d["appointments"].remove(next(a for a in d["appointments"] if a["role"] == "programmeResponsible"))
    add_person(d, "specialInstructor", degree=None, field=None)


def scenario_missing_year_and_inactive(d):
    del d["curricula"][0]["curriculumYear"]
    d["ps_requirements"][4]["active"] = False


@pytest.mark.parametrize("mutate", [scenario_base, scenario_fail_and_special_instructor, scenario_missing_year_and_inactive])
def test_the_document_never_changes_ps_evaluation(mutate):
    without = base_data()
    mutate(without)
    with_doc = with_readiness(copy.deepcopy(without))
    exclude = {"generation_readiness"}
    assert monitor(with_doc).model_dump(exclude=exclude) == monitor(without).model_dump(exclude=exclude)
    a, b = make_service(with_doc)[0], make_service(without)[0]
    for code in OWNER_REQUIRED_PS:
        assert a.ps_detail(code) == b.ps_detail(code)


def test_a_config_type_document_is_never_evaluated_as_a_ps_even_if_marked_active(data):
    doc = {**copy.deepcopy(GENERATION_READINESS), "active": True, "psCode": "x", "config": {}}
    resp = monitor(with_readiness(data, doc))
    assert [r.ps_code for r in resp.results] == OWNER_REQUIRED_PS
    assert make_service(data)[0].ps_detail("x") is None


# TEST 8
class RecordingDatabase:
    """Stands in for a pymongo Database: records which collection and query each read uses."""

    def __init__(self):
        self.reads = []
        self._name = None

    def __getitem__(self, name):
        self._name = name
        return self

    def find(self, query):
        self.reads.append((self._name, query))
        return iter([])


def test_8_the_document_is_read_from_the_existing_collection_only():
    db = RecordingDatabase()
    adapter = MongoConfigurationAdapter(db)
    adapter.read_active()
    adapter.read_by_code("x")
    adapter.read_by_type(CONFIG_TYPE)
    assert {name for name, _ in db.reads} == {"ps_requirements"} == {CONFIGURATION_COLLECTION}
    assert db.reads[-1] == ("ps_requirements", {"configType": "generationReadiness"})


def test_8_no_new_collection_is_declared_or_named_in_application_source():
    from app.models.source_schema import SOURCE_SCHEMA
    assert set(SOURCE_SCHEMA) == {"curricula", "persons", "educations", "appointments", "academic_works", "documents",
                                  "data_usages", "generated_documents"}
    # collection names the project owner ruled out, as string literals (the Python module name is not one)
    banned = re.compile(r"[\"'](generation_readiness|readiness_config|programme_readiness)[\"']", re.I)
    for path in APP_DIR.rglob("*.py"):
        text = path.read_text()
        assert not banned.search(text), path
        assert re.findall(r"CONFIGURATION_COLLECTION\s*=\s*[\"'](\w+)[\"']", text) in ([], ["ps_requirements"]), path


# TEST 9
def test_9_no_generation_readiness_value_is_hardcoded_in_application_source():
    for path in APP_DIR.rglob("*.py"):
        text = path.read_text()
        assert not [c for c in OWNER_REQUIRED_PS if c in text], path
        if path.name != "status.py":   # the Status enum is the only place the status names are spelled
            assert not re.search(r"[\"'](PASS|FAIL|REVIEW|N/A)[\"']", text), path


def test_9_statuses_that_allow_or_block_come_from_the_document(data):
    with_readiness(data)
    assert blocking(monitor(data)) == [("PS-03", Status.REVIEW), ("PS-06", Status.REVIEW)]
    when = readiness_body(data)["readyWhen"]
    when["allowedStatus"], when["blockedStatus"] = ["PASS", "REVIEW"], ["FAIL", "N/A"]
    resp = monitor(data)
    assert resp.generation_readiness.status is Readiness.NOT_READY and blocking(resp) == [("PS-08", Status.NA)]
    when["allowedStatus"], when["blockedStatus"] = ["PASS", "REVIEW", "N/A"], ["FAIL"]
    assert monitor(data).generation_readiness.status is Readiness.READY


def test_9_the_required_ps_come_from_the_document(data):
    with_readiness(data)
    data["ps_requirements"][2]["active"] = False                     # PS-03 configuration inactive
    assert blocking(monitor(data)) == [("PS-03", None), ("PS-06", Status.REVIEW)]      # still required: blocks
    readiness_body(data)["requiredPS"].remove("PS-03")
    assert blocking(monitor(data)) == [("PS-06", Status.REVIEW)]                         # PS-03 no longer required


def test_required_ps_may_be_fewer_than_the_active_configurations(data):
    """No rule makes every active PS required: the document's requiredPS alone is checked."""
    required = readiness_body(with_readiness(data))["requiredPS"]
    for code in ("PS-03", "PS-06"):                                  # active, REVIEW (user review), not required
        required.remove(code)
    gr = monitor(data).generation_readiness
    assert (gr.status, gr.blocking_ps, gr.issue, gr.detail) == (Readiness.READY, [], None, None)


def test_9_blocking_order_follows_required_ps(data):
    with_readiness(data)
    data["appointments"].remove(next(a for a in data["appointments"] if a["role"] == "programmeResponsible"))
    assert blocking(monitor(data)) == [("PS-01", Status.FAIL), ("PS-03", Status.REVIEW), ("PS-06", Status.REVIEW)]
    readiness_body(data)["requiredPS"].reverse()
    assert blocking(monitor(data)) == [("PS-06", Status.REVIEW), ("PS-03", Status.REVIEW), ("PS-01", Status.FAIL)]


# TEST 10
def test_10_a_missing_document_gives_no_decision_and_no_default(data):
    resp = monitor(data)
    gr = resp.generation_readiness
    assert gr.status is None and gr.blocking_ps == [] and gr.issue == "configuration_error"
    assert "no configuration document with configType 'generationReadiness'" in gr.detail
    assert [r.ps_code for r in resp.results] == OWNER_REQUIRED_PS


def test_10_a_document_without_config_type_is_not_found(data):
    doc = copy.deepcopy(GENERATION_READINESS)
    del doc["configType"]
    resp = monitor(with_readiness(data, doc))
    assert resp.generation_readiness.status is None and resp.generation_readiness.issue == "configuration_error"
    assert [r.ps_code for r in resp.results] == OWNER_REQUIRED_PS


def test_duplicate_documents_give_no_decision(data):
    with_readiness(with_readiness(data))
    gr = monitor(data).generation_readiness
    assert gr.status is None and gr.issue == "configuration_error" and "2 configuration documents" in gr.detail


# --- validation ---------------------------------------------------------------------------------
def _set(path, value):
    def mutate(doc):
        node = doc
        for key in path[:-1]:
            node = node[key]
        if value is _DELETE:
            del node[path[-1]]
        else:
            node[path[-1]] = value
    return mutate


_DELETE = object()
GR = "generationReadiness"
INVALID = {
    "no generationReadiness": (_set([GR], _DELETE), "generationReadiness is missing or not an object"),
    "generationReadiness not an object": (_set([GR], ["x"]), "generationReadiness is missing or not an object"),
    "requiredPS missing": (_set([GR, "requiredPS"], _DELETE), "requiredPS is missing or not an array"),
    "requiredPS not an array": (_set([GR, "requiredPS"], "PS-01"), "requiredPS is missing or not an array"),
    "requiredPS empty": (_set([GR, "requiredPS"], []), "requiredPS is empty"),
    "requiredPS not text": (_set([GR, "requiredPS"], ["PS-01", 2]), "requiredPS must list PS codes as text"),
    "readyWhen missing": (_set([GR, "readyWhen"], _DELETE), "readyWhen is missing or not an object"),
    "allowedStatus missing": (_set([GR, "readyWhen", "allowedStatus"], _DELETE),
                              "readyWhen.allowedStatus is missing, empty or not an array"),
    "allowedStatus empty": (_set([GR, "readyWhen", "allowedStatus"], []),
                            "readyWhen.allowedStatus is missing, empty or not an array"),
    "blockedStatus missing": (_set([GR, "readyWhen", "blockedStatus"], _DELETE),
                              "readyWhen.blockedStatus is missing, empty or not an array"),
    "blockedStatus not an array": (_set([GR, "readyWhen", "blockedStatus"], "FAIL"),
                                   "readyWhen.blockedStatus is missing, empty or not an array"),
    "unknown status": (_set([GR, "readyWhen", "allowedStatus"], ["PASS", "N/A", "OK"]),
                       "readyWhen.allowedStatus names unknown status(es) ['OK']; known: ['PASS', 'FAIL', 'REVIEW', 'N/A']"),
    "status both allowed and blocked": (_set([GR, "readyWhen", "blockedStatus"], ["FAIL", "REVIEW", "PASS"]),
                                        "status(es) ['PASS'] are both allowedStatus and blockedStatus"),
    "requiredAll missing": (_set([GR, "requiredAll"], _DELETE), "requiredAll is missing or not a boolean"),
    "requiredAll not boolean": (_set([GR, "requiredAll"], "true"), "requiredAll is missing or not a boolean"),
}


@pytest.mark.parametrize("case", list(INVALID))
def test_an_invalid_document_is_a_configuration_error_and_leaves_ps_results_alone(data, case):
    mutate, detail = INVALID[case]
    doc = copy.deepcopy(GENERATION_READINESS)
    mutate(doc)
    expected_results = monitor(copy.deepcopy(data)).results
    resp = monitor(with_readiness(data, doc))
    gr = resp.generation_readiness
    assert (gr.status, gr.issue, gr.detail, gr.blocking_ps) == (None, "configuration_error", detail, [])
    assert resp.results == expected_results


def test_required_all_false_is_not_decided_but_reported_for_a_decision(data):
    doc = copy.deepcopy(GENERATION_READINESS)
    doc[GR]["requiredAll"] = False
    gr = monitor(with_readiness(data, doc), manual=ManualResults({"PS-03": "PASS", "PS-06": "PASS"})).generation_readiness
    assert (gr.status, gr.blocking_ps, gr.issue) == (None, [], "spec_gap")
    assert gr.detail == "requiredAll is false: no rule is defined for it, so nothing is decided (decision needed)"


@pytest.mark.parametrize("mutate", [_set([GR, "minimumPass"], 8), _set([GR, "readyWhen", "warnStatus"], ["REVIEW"])])
def test_keys_no_requirement_names_are_not_read(data, mutate):
    plain = monitor(with_readiness(copy.deepcopy(data))).generation_readiness
    doc = copy.deepcopy(GENERATION_READINESS)
    mutate(doc)
    assert monitor(with_readiness(data, doc)).generation_readiness == plain


@pytest.mark.parametrize("doc, detail", [
    ({GR: GENERATION_READINESS[GR]}, "configType is missing"),
    ({"configType": "other", GR: GENERATION_READINESS[GR]}, "configType is 'other', not 'generationReadiness'"),
])
def test_the_document_itself_must_carry_its_config_type(doc, detail):
    with pytest.raises(ReadinessConfigProblem) as problem:
        validate(doc)
    assert problem.value.issue == "configuration_error" and problem.value.detail == detail


# --- decision over real evaluation results --------------------------------------------------------
def test_review_blocks_and_not_applicable_does_not(data):
    resp = monitor(with_readiness(data))
    statuses = {r.ps_code: r.status for r in resp.results}
    assert statuses["PS-03"] is statuses["PS-06"] is Status.REVIEW and statuses["PS-08"] is Status.NA
    assert resp.generation_readiness.status is Readiness.NOT_READY
    assert blocking(resp) == [("PS-03", Status.REVIEW), ("PS-06", Status.REVIEW)]


def test_all_required_ps_allowed_is_ready(data):
    # PS-03 and PS-06 are user reviews; the result the reviewer chose comes through the manual-result port.
    resp = monitor(with_readiness(data), manual=ManualResults({"PS-03": "PASS", "PS-06": "PASS"}))
    assert {r.status for r in resp.results} == {Status.PASS, Status.NA}
    gr = resp.generation_readiness
    assert (gr.status, gr.blocking_ps, gr.issue, gr.detail) == (Readiness.READY, [], None, None)


def test_fail_blocks(data):
    with_readiness(data)
    data["appointments"].remove(next(a for a in data["appointments"] if a["role"] == "programmeResponsible"))
    resp = monitor(data, manual=ManualResults({"PS-03": "PASS", "PS-06": "PASS"}))
    assert resp.generation_readiness.status is Readiness.NOT_READY and blocking(resp) == [("PS-01", Status.FAIL)]


def test_a_required_ps_without_active_configuration_is_a_configuration_problem_and_not_ready(data):
    with_readiness(data)
    data["ps_requirements"][4]["active"] = False                     # PS-05
    gr = monitor(data, manual=ManualResults({"PS-03": "PASS", "PS-06": "PASS"})).generation_readiness
    assert (gr.status, gr.issue) == (Readiness.NOT_READY, "configuration_error")
    assert [(b.ps_code, b.status) for b in gr.blocking_ps] == [("PS-05", None)]
    assert gr.detail == "requiredPS ['PS-05'] have no active PS configuration"


def test_a_required_ps_with_no_configuration_at_all_is_a_configuration_problem(data):
    readiness_body(with_readiness(data))["requiredPS"].append("PS-99")
    gr = monitor(data, manual=ManualResults({"PS-03": "PASS", "PS-06": "PASS"})).generation_readiness
    assert (gr.status, gr.issue) == (Readiness.NOT_READY, "configuration_error")
    assert [(b.ps_code, b.status) for b in gr.blocking_ps] == [("PS-99", None)]


def test_no_curriculum_means_no_result_for_any_required_ps_a_data_problem():
    data = with_readiness({"ps_requirements": copy.deepcopy(AUTHORITATIVE_CONFIG)})
    resp = monitor(data)
    assert resp.curriculum is None and resp.results == []
    gr = resp.generation_readiness
    assert (gr.status, gr.issue) == (Readiness.NOT_READY, None)
    assert blocking(resp) == [(code, None) for code in OWNER_REQUIRED_PS]
    assert gr.detail == f"requiredPS {OWNER_REQUIRED_PS} have no evaluation result"


def test_lists_need_not_name_every_status(data):
    """No rule requires allowedStatus + blockedStatus to cover every status (project owner, 2026-09-26)."""
    when = readiness_body(with_readiness(data))["readyWhen"]
    when["allowedStatus"] = ["PASS"]                                 # N/A is neither allowed nor blocked
    assert blocking(monitor(data)) == [("PS-03", Status.REVIEW), ("PS-06", Status.REVIEW)]   # a blocked status still decides NOT_READY
    gr = monitor(data, manual=ManualResults({"PS-03": "PASS", "PS-06": "PASS"})).generation_readiness
    # PS-08 is N/A, which neither list names: not READY (not every status allowed), and no rule decides the rest
    assert (gr.status, gr.blocking_ps, gr.issue) == (None, [], "spec_gap")
    assert gr.detail.startswith("the status of ['PS-08'] is neither an allowedStatus nor a blockedStatus")


# --- API ------------------------------------------------------------------------------------------
def test_api_monitor_carries_generation_readiness(data):
    body = client_for(make_service(with_readiness(data))[0]).get("/api/monitor").json()
    assert body["generationReadiness"] == {"status": "NOT_READY", "blockingPS": [{"psCode": "PS-03", "status": "REVIEW"},
                                                                                 {"psCode": "PS-06", "status": "REVIEW"}],
                                           "issue": None, "detail": None}
    assert len(body["results"]) == 9 and body["overallStatus"] is None


@pytest.mark.parametrize("code", OWNER_REQUIRED_PS)
def test_api_ps_detail_is_unchanged(data, code):
    before = client_for(make_service(copy.deepcopy(data))[0]).get(f"/api/monitor/ps/{code}").json()
    after = client_for(make_service(with_readiness(data))[0]).get(f"/api/monitor/ps/{code}").json()
    assert after == before and "generationReadiness" not in after


def test_api_missing_document_is_reported_not_failed(data):
    r = client_for(make_service(data)[0]).get("/api/monitor")
    assert r.status_code == 200
    assert r.json()["generationReadiness"]["status"] is None
    assert r.json()["generationReadiness"]["issue"] == "configuration_error"


class ReadinessUnreadable(InMemoryConfigurationAdapter):
    def read_by_type(self, config_type):
        raise DataSourceError("connection refused")


def test_api_unreadable_document_is_503_not_fail(data):
    service = MonitoringService(ConfigurationRepository(ReadinessUnreadable(with_readiness(data)["ps_requirements"])),
                                SourceDataRepository(InMemorySourceAdapter(data)))
    r = client_for(service).get("/api/monitor")
    assert r.status_code == 503 and r.json() == {"detail": "Unable to load monitoring data"}
    assert "FAIL" not in r.text
