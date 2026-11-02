import copy
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_service
from app.main import create_app
from app.models.status import Status
from app.repositories.configuration import ConfigurationRepository
from app.repositories.source_data import SourceDataRepository
from app.services.monitoring_service import MonitoringService
from tests.support.fixtures import make_service, results
from tests.support.memory_store import (
    FailingConfigurationAdapter, FailingSourceAdapter, InMemoryConfigurationAdapter, InMemorySourceAdapter,
)

APP_DIR = Path(__file__).resolve().parents[1] / "app"


def client_for(service):
    app = create_app()
    app.dependency_overrides[get_service] = lambda: service
    return TestClient(app)


# --- configuration is read from the DB ------------------------------------------
def test_configuration_is_read_through_the_configuration_repository(data):
    config = InMemoryConfigurationAdapter(data["ps_requirements"])
    service = MonitoringService(ConfigurationRepository(config), SourceDataRepository(InMemorySourceAdapter(data)))
    service.monitor()
    service.ps_detail("PS-01")
    # read_by_type: the generation readiness document of the same collection (monitor only)
    assert config.calls == ["read_active", "read_by_type", "read_by_code"]


def test_only_active_configuration_is_evaluated(data):
    data["ps_requirements"][2]["active"] = False
    assert "PS-03" not in results(data) and len(results(data)) == 8


def test_inactive_configuration_is_never_evaluated_even_if_the_adapter_returns_it(data):
    data["ps_requirements"][2]["active"] = False
    service, _ = make_service(data, leak_inactive=True)
    assert "PS-03" not in {r.ps_code for r in service.monitor().results}
    assert service.ps_detail("PS-03") is None


def test_result_set_follows_configuration_documents(data):
    data["ps_requirements"] = data["ps_requirements"][:2]
    assert set(results(data)) == {"PS-01", "PS-02"}


def test_requirement_text_and_checks_come_from_configuration(data):
    data["ps_requirements"][0]["requirement"] = "changed in DB"
    data["ps_requirements"][0]["config"]["condition"]["value"] = 6
    r = results(data)["PS-01"]
    assert r.requirement == "changed in DB"
    assert "condition.value: 6" in r.checks and "targetCollection: \"appointments\"" in r.checks


# --- configuration problems are reported, not guessed --------------------------------
CODES = [f"PS-0{i}" for i in range(1, 10)]


def mutate_config(data, code, fn):
    fn(next(d["config"] for d in data["ps_requirements"] if d["psCode"] == code))


def first_line(r):
    return r.missing_information[0]


def test_unrecognised_configuration_is_spec_gap_review(data):
    data["ps_requirements"][0]["config"] = {"result": {"review": "REVIEW"}, "somethingNew": True}
    r = results(data)["PS-01"]
    assert r.status is Status.REVIEW and first_line(r).startswith("SPEC GAP")
    assert "somethingNew" in " ".join(r.missing_information)


def test_incomplete_construct_is_a_configuration_error(data):
    del data["ps_requirements"][0]["config"]["condition"]["value"]
    r = results(data)["PS-01"]
    assert r.status is Status.REVIEW and first_line(r).startswith("Configuration error")


def test_missing_config_block_is_configuration_error(data):
    del data["ps_requirements"][0]["config"]
    assert "Configuration error" in first_line(results(data)["PS-01"])


def test_missing_result_map_is_a_configuration_error(data):
    del data["ps_requirements"][0]["config"]["result"]
    r = results(data)["PS-01"]
    assert r.status is Status.REVIEW and any("result" in m for m in r.missing_information)


def test_unsupported_operator_is_spec_gap(data):
    data["ps_requirements"][0]["config"]["condition"]["operator"] = "~="
    r = results(data)["PS-01"]
    assert first_line(r).startswith("SPEC GAP") and r.data_found == []


@pytest.mark.parametrize("code", CODES)
def test_unknown_top_level_key_makes_every_ps_review_with_spec_gap(data, code):
    mutate_config(data, code, lambda c: c.update(bogusKey=True))
    r = results(data)[code]
    assert r.status is Status.REVIEW
    assert any(m.startswith("SPEC GAP") and "bogusKey" in m for m in r.missing_information)
    assert r.data_found == [] and r.verification.found == 0            # nothing evaluated, nothing read


@pytest.mark.parametrize("code,path", [("PS-01", ("condition",)), ("PS-01", ("count",)), ("PS-09", ("comparison",)),
                                       ("PS-09", ("year",)), ("PS-09", ("calculation",)), ("PS-04", ("appointmentOrder",))])
def test_unknown_nested_key_is_a_spec_gap(data, code, path):
    mutate_config(data, code, lambda c: c[path[0]].update(bogus=1))
    assert f"{path[0]}.bogus" in " ".join(results(data)[code].missing_information)


def test_two_operation_constructs_at_once_are_ambiguous_not_guessed(data):
    data["ps_requirements"][0]["config"]["requiredFields"] = ["personId"]
    r = results(data)["PS-01"]
    assert r.status is Status.REVIEW and "exactly one operation" in " ".join(r.missing_information)
    assert r.data_found == []


def test_no_operation_construct_is_a_spec_gap(data):
    del data["ps_requirements"][0]["config"]["count"]
    assert "exactly one operation" in " ".join(results(data)["PS-01"].missing_information)


def test_na_enabled_has_no_generic_meaning(data):
    data["ps_requirements"][0]["config"]["naEnabled"] = True
    assert "naEnabled" in " ".join(results(data)["PS-01"].missing_information)


def test_filter_with_a_non_scalar_value_is_a_spec_gap(data):
    data["ps_requirements"][0]["config"]["filter"]["role"] = ["programmeResponsible", "programmeStaff"]
    assert "SPEC GAP" in first_line(results(data)["PS-01"])


def test_target_collection_outside_source_data_is_a_configuration_error(data):
    data["ps_requirements"][0]["config"]["targetCollection"] = "ps_requirements"
    assert first_line(results(data)["PS-01"]).startswith("Configuration error")


def test_interpretation_needs_no_data_and_no_ps_code(data):
    """The interpreter maps configuration to a request on its own; the PS code plays no part."""
    from app.monitoring.interpreter import ConfigurationInterpreter
    ps01 = next(d for d in data["ps_requirements"] if d["psCode"] == "PS-01")
    plan = ConfigurationInterpreter().interpret(ps01["config"])
    assert plan.request is not None and plan.gaps == [] and plan.errors == []
    ps01["psCode"] = "anything-at-all"
    assert results(data)["anything-at-all"].status is Status.PASS


# --- curriculum selection ---------------------------------------------------------------
def with_two_curricula(data):
    other = copy.deepcopy(data["curricula"][0])
    other.update(_id=type(data["curricula"][0]["_id"])(), curriculumCode="OTHER")
    data["curricula"].append(other)


@pytest.mark.parametrize("path", ["/api/monitor", "/api/monitor/ps/PS-01"])
def test_several_curricula_without_a_selection_is_a_spec_gap_not_a_guess(data, path):
    with_two_curricula(data)
    service, _ = make_service(data)
    r = client_for(service).get(path)
    assert r.status_code == 409 and r.json()["detail"].startswith("SPEC GAP")


def test_a_single_curriculum_needs_no_selection(data):
    service, _ = make_service(data)
    assert client_for(service).get("/api/monitor").status_code == 200


def test_missing_information_marks_incomplete(data):
    del data["curricula"][0]["curriculumYear"]
    service, _ = make_service(data)
    resp = service.monitor()
    assert resp.data_completeness == "incomplete"
    assert resp.overall_status is None   # overall-status rule is a SPEC GAP


def test_traceability_lists_source_records_read(data):
    r = results(data)["PS-01"]
    assert r.traceability and {t.collection for t in r.traceability} == {"appointments"}
    assert r.evidence == []
    assert r.verification.found == len(r.traceability)
    assert r.verification.verified is None and r.verification.approved is None


# --- API --------------------------------------------------------------------------
def test_api_monitor_shape(data):
    service, _ = make_service(data)
    body = client_for(service).get("/api/monitor").json()
    assert body["curriculum"]["curriculumName"] == data["curricula"][0]["curriculumName"]
    assert body["overallStatus"] is None and len(body["results"]) == 9
    assert {"psCode", "status", "requirement", "checks", "dataSummary", "dataFound", "verification",
            "missingInformation", "evidence", "traceability", "dataCompleteness"} <= body["results"][0].keys()


def test_api_empty_database_returns_no_curriculum():
    service, _ = make_service({})
    body = client_for(service).get("/api/monitor").json()
    assert body["curriculum"] is None and body["results"] == []


def test_api_ps_detail_and_404(data):
    service, _ = make_service(data)
    c = client_for(service)
    assert c.get("/api/monitor/ps/PS-01").json()["psCode"] == "PS-01"
    assert c.get("/api/monitor/ps/PS-99").status_code == 404


def test_api_selects_curriculum_by_code(data):
    other = copy.deepcopy(data["curricula"][0])
    other.update(_id=data["curricula"][0]["_id"].__class__(), curriculumCode="OTHER")
    data["curricula"].append(other)
    service, _ = make_service(data)
    assert client_for(service).get("/api/monitor?curriculumCode=OTHER").json()["curriculum"]["curriculumCode"] == "OTHER"


# --- backend failure is never FAIL ---------------------------------------------------
def failing_services(data):
    good_config = InMemoryConfigurationAdapter(data["ps_requirements"])
    good_source = InMemorySourceAdapter(data)
    return {
        "source": MonitoringService(ConfigurationRepository(good_config), SourceDataRepository(FailingSourceAdapter())),
        "configuration": MonitoringService(ConfigurationRepository(FailingConfigurationAdapter()), SourceDataRepository(good_source)),
    }


@pytest.mark.parametrize("which", ["source", "configuration"])
@pytest.mark.parametrize("path", ["/api/monitor", "/api/monitor/ps/PS-01"])
def test_data_source_error_is_503_not_fail(data, which, path):
    r = client_for(failing_services(data)[which]).get(path)
    assert r.status_code == 503 and r.json() == {"detail": "Unable to load monitoring data"}
    assert "FAIL" not in r.text


# --- read-only ------------------------------------------------------------------------
def test_monitoring_run_only_reads(data):
    service, source = make_service(data)
    service.monitor()
    assert {op for op, _ in source.calls} == {"find"}


def test_source_data_and_configuration_unchanged_after_run(data):
    before = copy.deepcopy(data)
    make_service(data)[0].monitor()
    assert data == before


# Project owner, 2026-09-26 (SET 4, 5, 6): the routes that are not GET record what the user did (a verification,
# a review, saving the monitoring result) in the Monitor-owned store; every other route only reads.
WRITE_ROUTES = {"/api/monitor/ps/{ps_code}/verification", "/api/monitor/ps/{ps_code}/review", "/api/monitor/results"}
# Project owner, 2026-10-04 (Authentication): not GET either, but these write nothing to monitoring_results —
# login/logout only set or clear the caller's own session cookie.
AUTH_ROUTES = {"/api/auth/login", "/api/auth/logout"}


def test_only_the_monitor_owned_write_routes_are_not_get():
    paths = create_app().openapi()["paths"]
    methods = {(path, m) for path, ops in paths.items() for m in ops}
    not_get = WRITE_ROUTES | AUTH_ROUTES
    assert {pm for pm in methods if pm[1] != "get"} == {(path, "post") for path in not_get}
    assert paths and {m for path, m in methods if path not in not_get} == {"get"}


def test_repositories_and_adapters_expose_only_read_operations():
    from app.adapters.mongo import MongoConfigurationAdapter, MongoSourceDataAdapter
    public = lambda cls: {n for n in dir(cls) if not n.startswith("_")}
    assert public(MongoSourceDataAdapter) == {"find"}
    assert public(MongoConfigurationAdapter) == {"read_active", "read_by_code", "read_by_type"}
    assert public(SourceDataRepository) == {"find", "find_curricula"}
    assert public(ConfigurationRepository) == {"load_active_requirements", "get_requirement", "load_by_type"}


WRITES = re.compile(r"\.(insert_one|insert_many|update_one|update_many|replace_one|delete_one|delete_many|"
                    r"bulk_write|find_one_and_\w+|drop|create_index|save)\(")
# Project owner, 2026-09-26 (SET 4): writing is allowed only in the Monitor-owned persistence adapter and only
# to `monitoring_results`. Source Data and Configuration stay read only.
MONITOR_WRITER = APP_DIR / "adapters" / "monitoring_results.py"
# Project owner, 2026-10-05 (logout revocation, Finding #2): the only other write in the application — one
# timestamp field of `users`, set by a logout, so a captured cookie stops verifying immediately. Never an
# account's username, password or name; those stay seed-script-only (scripts/seed_user.py).
AUTH_WRITER = APP_DIR / "adapters" / "auth.py"
WRITERS = {MONITOR_WRITER, AUTH_WRITER}


def test_no_write_calls_outside_the_monitor_owned_persistence_adapter():
    for path in APP_DIR.rglob("*.py"):
        if path not in WRITERS:
            assert not WRITES.search(path.read_text()), path


def test_the_monitor_owned_adapter_writes_only_monitoring_results_and_deletes_nothing():
    from app.adapters.mongo import CONFIGURATION_COLLECTION
    from app.adapters.monitoring_results import MONITORING_RESULTS_COLLECTION, MongoMonitoringResultAdapter
    from app.repositories.source_data import SOURCE_COLLECTIONS
    text = MONITOR_WRITER.read_text()
    assert MONITORING_RESULTS_COLLECTION == "monitoring_results"
    assert MONITORING_RESULTS_COLLECTION not in SOURCE_COLLECTIONS | {CONFIGURATION_COLLECTION}
    assert re.findall(r"database\[(\w+)\]", text) == ["MONITORING_RESULTS_COLLECTION"]   # its one collection
    assert not [n for n in SOURCE_COLLECTIONS | {CONFIGURATION_COLLECTION} if f'"{n}"' in text]
    assert {m.group(1) for m in WRITES.finditer(text)} == {"update_one", "bulk_write", "create_index"}  # upserts only
    assert text.count("UpdateOne(") == 1 and not re.search(r"DeleteOne|DeleteMany|ReplaceOne|InsertOne", text)
    assert {n for n in dir(MongoMonitoringResultAdapter) if not n.startswith("_")} == {"read", "set_verified", "set_review", "set_results"}


def test_the_auth_adapter_writes_only_one_field_of_users_and_deletes_nothing():
    """Finding #2: the application's one other write stays as narrow as the review/verification ones — a
    single field, no account data, no delete."""
    from app.adapters.auth import USERS_COLLECTION
    text = AUTH_WRITER.read_text()
    assert USERS_COLLECTION == "users"
    assert {m.group(1) for m in WRITES.finditer(text)} == {"update_one"}   # one field, no insert/delete/replace
    assert re.findall(r"database\[(\w+)\]", text) == []                   # it reads/writes self._db[USERS_COLLECTION]
    assert text.count('self._db[USERS_COLLECTION].update_one(') == 1
    assert re.search(r'"\$set":\s*\{"sessionsInvalidBefore":\s*at\}', text)
    for field in ("username", "passwordHash", '"name"'):
        assert field not in text.split("update_one(", 1)[1]               # the write touches no account field


# --- no hard-coded PS business behaviour ----------------------------------------------------
def test_no_ps_code_selects_logic_anywhere_in_application_source():
    banned = re.compile(r"PS-\d|PS\d\d|(ps_code|psCode)\s*(==|!=)|match\s+ps|\[[^\]]*(ps_code|psCode)|\bpsCode\b.*\bin\b", re.I)
    for path in APP_DIR.rglob("*.py"):
        for line in path.read_text().splitlines():
            assert not banned.search(line), (path, line)


def test_no_local_ps_configuration_outside_test_fixtures():
    root = APP_DIR.parents[0]
    installed = lambda p: any(part.startswith((".venv", "venv")) or part == "site-packages" for part in p.parts)  # noqa: E731
    outside = [p for p in root.rglob("*.json") if not installed(p) and "fixtures" not in p.parts]
    assert outside == [] and not (APP_DIR / "config").exists()
