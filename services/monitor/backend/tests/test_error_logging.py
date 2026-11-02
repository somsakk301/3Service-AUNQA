"""Error logging (SET 8, project owner 2026-09-26): errors only, standard logging, local handler only.

Covered: Data Source Error / Connection Error (ERROR, every 503), Monitor-owned write failures, System Error
(unhandled exception, ERROR, 500), Evaluation Error (ERROR, one PS), Configuration Error (WARNING, the request still
answers). A PS status is a result, not an error, and is never logged. Responses stay exactly as they were.
"""
import copy
import logging
import re
import socket
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pymongo import MongoClient
from pymongo.errors import AutoReconnect, OperationFailure, ServerSelectionTimeoutError

from app.adapters.mongo import MongoConfigurationAdapter, MongoSourceDataAdapter, source_error
from app.api.dependencies import get_current_user, get_service
from app.error_log import FORMAT, LOGGER, RedactingFormatter, configure_logging
from app.main import create_app
from app.models.auth import AuthenticatedUser
from app.repositories.base import DataSourceConnectionError, DataSourceError
from app.repositories.configuration import ConfigurationRepository
from app.repositories.monitoring_results import MonitoringResultRepository
from app.repositories.source_data import SourceDataRepository
from app.services.monitoring_service import MonitoringService
from tests.support.fixtures import GENERATION_READINESS, add_person, make_service, oid
from tests.support.memory_store import (
    FailingSourceAdapter, InMemoryConfigurationAdapter, InMemoryMonitoringResultAdapter, InMemorySourceAdapter,
)

APP_DIR = Path(__file__).resolve().parents[1] / "app"
TEST_USER = AuthenticatedUser(user_id="507f1f77bcf86cd799439011", name="ผู้ตรวจทดสอบ")


def client_for(service, **kw):
    app = create_app()
    app.dependency_overrides[get_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: TEST_USER
    return TestClient(app, **kw)


def prepared(data):
    data["ps_requirements"].append(copy.deepcopy(GENERATION_READINESS))
    data["documents"] = [{"_id": oid(), "documentType": "curriculum", "fileType": "pdf", "fileName": "TEST-1.pdf",
                          "curriculumId": data["curricula"][0]["_id"],
                          "originalFile": {"storage": "local", "path": "test-data/documents/original/TEST-1.pdf"}}]
    return data


def app_records(caplog, level=logging.WARNING):
    return [r for r in caplog.records if r.name.startswith(LOGGER + ".") and r.levelno >= level]


def formatted(record):
    return RedactingFormatter(FORMAT).format(record)


# --- Data Source / Connection Error: every 503 is logged, the response is unchanged ------------------------------
@pytest.mark.parametrize("path", ["/api/monitor?curriculumCode=C1", "/api/monitor/ps/PS-01?curriculumCode=C1"])
def test_a_database_read_failure_is_logged_and_still_503(data, caplog, path):
    service = MonitoringService(ConfigurationRepository(InMemoryConfigurationAdapter(data["ps_requirements"])),
                                SourceDataRepository(FailingSourceAdapter()))
    with caplog.at_level(logging.WARNING):
        r = client_for(service).get(path)
    assert r.status_code == 503 and r.json() == {"detail": "Unable to load monitoring data"}
    [record] = app_records(caplog)
    assert (record.levelno, record.name, record.category) == (logging.ERROR, "app.api.routes.monitor", "data_source_error")
    assert record.exc_info and isinstance(record.exc_info[1], DataSourceError)
    assert record.getMessage() == f"GET {path.split('?')[0]} failed (curriculumCode=C1): Unable to load monitoring data"
    assert "Traceback" in formatted(record) and "Traceback" not in r.text


def _closed_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_an_unreachable_database_is_a_connection_error(caplog):
    database = MongoClient(f"mongodb://127.0.0.1:{_closed_port()}", serverSelectionTimeoutMS=100)["nothing"]
    service = MonitoringService(ConfigurationRepository(MongoConfigurationAdapter(database)),
                                SourceDataRepository(MongoSourceDataAdapter(database)))
    with caplog.at_level(logging.WARNING):
        r = client_for(service).get("/api/monitor")
    assert r.status_code == 503 and r.json() == {"detail": "Unable to load monitoring data"}
    [record] = app_records(caplog)
    assert (record.levelno, record.category) == (logging.ERROR, "connection_error")
    assert isinstance(record.exc_info[1], DataSourceConnectionError)
    assert isinstance(record.exc_info[1].__cause__, ServerSelectionTimeoutError)


@pytest.mark.parametrize("error, kind", [(ServerSelectionTimeoutError("x"), DataSourceConnectionError),
                                         (AutoReconnect("x"), DataSourceConnectionError),
                                         (OperationFailure("x"), DataSourceError)])
def test_driver_errors_are_told_apart(error, kind):
    assert type(source_error(error)) is kind


@pytest.mark.parametrize("method, path, body, detail", [
    ("post", "/api/monitor/ps/PS-01/verification", None, "Unable to save the verification"),
    ("post", "/api/monitor/ps/PS-03/review", {"status": "PASS"}, "Unable to save the review"),
    ("post", "/api/monitor/results", None, "Unable to save the monitoring result"),
])
def test_a_monitoring_results_failure_is_logged_and_still_503(data, caplog, method, path, body, detail):
    service, _ = make_service(prepared(data), results=MonitoringResultRepository(InMemoryMonitoringResultAdapter(fail=True)))
    with caplog.at_level(logging.WARNING):
        r = getattr(client_for(service), method)(path, json=body) if body else getattr(client_for(service), method)(path)
    assert r.status_code == 503 and r.json() == {"detail": detail}
    [record] = app_records(caplog)
    assert (record.levelno, record.category) == (logging.ERROR, "data_source_error")
    assert record.getMessage() == f"POST {path} failed (curriculumCode=None): {detail}"


# --- System Error: an exception no route handles ----------------------------------------------------------------
def test_an_unexpected_exception_is_logged_and_answered_500_as_before(data, caplog, monkeypatch):
    service, _ = make_service(prepared(data))
    monkeypatch.setattr(service, "monitor", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    with caplog.at_level(logging.WARNING):
        r = client_for(service).get("/api/monitor?curriculumCode=C1")
    assert (r.status_code, r.text, r.headers["content-type"]) == (500, "Internal Server Error", "text/plain; charset=utf-8")
    [record] = app_records(caplog)
    assert (record.levelno, record.name, record.category) == (logging.ERROR, "app.main", "system_error")
    assert record.getMessage() == "Unexpected error in GET /api/monitor"            # path only, no query
    assert isinstance(record.exc_info[1], RuntimeError) and "RuntimeError: boom" in formatted(record)
    assert "boom" not in r.text and "Traceback" not in r.text


# --- Evaluation Error / Configuration Error ------------------------------------------------------------------
def test_an_evaluation_error_is_logged_for_that_ps_only(data, caplog, monkeypatch):
    from app.monitoring.engine import MonitoringEngine
    real = MonitoringEngine._execute

    def failing(self, req, ctx, key):
        if key == data["ps_requirements"][8]["psCode"]:
            raise RuntimeError("unexpected")
        return real(self, req, ctx, key)

    monkeypatch.setattr(MonitoringEngine, "_execute", failing)
    service, _ = make_service(prepared(data))
    with caplog.at_level(logging.WARNING):
        body = client_for(service).get("/api/monitor").json()
    assert body["results"][8]["issue"] == "evaluation_error" and body["results"][8]["status"] == "REVIEW"
    [record] = app_records(caplog)
    assert (record.levelno, record.name, record.category) == (logging.ERROR, "app.monitoring.engine", "evaluation_error")
    assert record.exc_info and "RuntimeError: unexpected" in formatted(record)


def test_a_configuration_error_is_a_warning_and_the_answer_is_unchanged(data, caplog):
    data["ps_requirements"][0]["config"] = {"result": {"review": "REVIEW"}, "count": {"field": 1}}   # malformed
    service, _ = make_service(prepared(data))
    with caplog.at_level(logging.WARNING):
        r = client_for(service).get("/api/monitor")
    assert r.status_code == 200 and r.json()["results"][0]["issue"] == "configuration_error"
    [record] = app_records(caplog)
    assert (record.levelno, record.category) == (logging.WARNING, "configuration_error")
    assert record.getMessage().startswith("configuration of PS-01 cannot be used: Configuration error:")


def test_a_missing_generation_readiness_configuration_is_a_warning(data, caplog):
    service, _ = make_service(data)                                           # no generationReadiness document
    with caplog.at_level(logging.WARNING):
        assert client_for(service).get("/api/monitor").json()["generationReadiness"]["status"] is None
    [record] = app_records(caplog)
    assert (record.levelno, record.category) == (logging.WARNING, "configuration_error")
    assert "generation readiness configuration cannot be used" in record.getMessage()


# --- results and client errors are not errors -------------------------------------------------------------------
def test_pass_fail_review_and_na_are_never_logged(data, caplog):
    data["appointments"].remove(next(a for a in data["appointments"] if a["role"] == "programmeResponsible"))
    add_person(data, "specialInstructor", degree=None, field=None)
    service, _ = make_service(prepared(data), results=MonitoringResultRepository(InMemoryMonitoringResultAdapter()))
    c = client_for(service)
    with caplog.at_level(logging.DEBUG):
        statuses = {r["status"] for r in c.get("/api/monitor").json()["results"]}
        for code in ("PS-01", "PS-03", "PS-08"):
            c.get(f"/api/monitor/ps/{code}")
        c.post("/api/monitor/ps/PS-03/verification")
        c.post("/api/monitor/ps/PS-03/review", json={"status": "FAIL"})
        c.post("/api/monitor/results")
    assert {"PASS", "FAIL", "REVIEW"} <= statuses
    assert app_records(caplog, logging.DEBUG) == []


def test_client_errors_are_not_logged(data, caplog):
    other = copy.deepcopy(data["curricula"][0])
    other.update(_id=oid(), curriculumCode="OTHER")
    data["curricula"].append(other)
    service, _ = make_service(prepared(data), results=MonitoringResultRepository(InMemoryMonitoringResultAdapter()))
    c = client_for(service)
    with caplog.at_level(logging.DEBUG):
        assert c.get("/api/monitor").status_code == 409
        assert c.get("/api/monitor/ps/PS-99?curriculumCode=OTHER").status_code == 404
        assert c.post("/api/monitor/ps/PS-01/review?curriculumCode=OTHER", json={"status": "PASS"}).status_code == 400
        assert c.post("/api/monitor/ps/PS-03/review?curriculumCode=OTHER", json={"status": "OK"}).status_code == 422
        assert c.get("/api/monitor/results").status_code == 405
    assert app_records(caplog, logging.DEBUG) == []


# --- what a log line holds, and what it never holds -----------------------------------------------------------------
def test_a_log_line_has_time_level_module_category_and_message():
    record = logging.LogRecord("app.api.routes.monitor", logging.ERROR, __file__, 1, "GET /api/monitor failed", (), None)
    record.category = "data_source_error"
    line = formatted(record)
    assert re.fullmatch(r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d,\d{3} ERROR app\.api\.routes\.monitor \[data_source_error\] "
                        r"GET /api/monitor failed", line)
    plain = logging.LogRecord("app.x", logging.WARNING, __file__, 1, "m", (), None)
    assert " [-] m" in formatted(plain)                                        # a record without a category


def test_credentials_in_a_connection_string_are_masked(caplog):
    service = MonitoringService(ConfigurationRepository(InMemoryConfigurationAdapter([])),
                                SourceDataRepository(_Failing("mongodb://admin:s3cret@db.example:27017/src failed")))
    with caplog.at_level(logging.WARNING):
        client_for(service).get("/api/monitor")
    [record] = app_records(caplog)
    line = formatted(record)
    assert "s3cret" not in line and "admin:" not in line and "mongodb://***@db.example:27017" in line


class _Failing(InMemorySourceAdapter):
    def __init__(self, message):
        super().__init__({})
        self.message = message

    def find(self, collection, query):
        raise DataSourceError(self.message)


def test_no_header_cookie_body_or_document_reaches_the_log(data, caplog, monkeypatch):
    service, _ = make_service(prepared(data), results=MonitoringResultRepository(InMemoryMonitoringResultAdapter(fail=True)))
    c = client_for(service)
    headers = {"Authorization": "Bearer tok-123", "Cookie": "session=cookie-456", "X-Api-Key": "key-789"}
    with caplog.at_level(logging.DEBUG):
        c.post("/api/monitor/ps/PS-03/review?curriculumCode=" + data["curricula"][0]["curriculumCode"],
               json={"status": "PASS", "note": "body-secret"}, headers=headers)
        monkeypatch.setattr(service, "ps_detail", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))
        c.get("/api/monitor/ps/PS-01?secret=query-999", headers=headers)
    text = "\n".join(formatted(r) for r in app_records(caplog, logging.DEBUG))
    assert len(app_records(caplog)) == 2
    for leaked in ("tok-123", "cookie-456", "key-789", "body-secret", "query-999", "TEST-1.pdf",
                   "test-data/documents", data["curricula"][0]["curriculumName"]):
        assert leaked not in text


# --- local only: one handler, no log collection, nothing sent out --------------------------------------------------
def test_the_handler_is_configured_once_and_is_local():
    configure_logging()
    create_app()
    handlers = [h for h in logging.getLogger(LOGGER).handlers if getattr(h, "_mornitor", False)]
    assert len(handlers) == 1 and type(handlers[0]) is logging.StreamHandler
    assert logging.getLogger(LOGGER).level == logging.WARNING


def test_logging_writes_no_collection_and_calls_no_service():
    text = "\n".join(p.read_text() for p in APP_DIR.rglob("*.py"))
    assert not re.search(r"HTTPHandler|SysLogHandler|SMTPHandler|SocketHandler|QueueHandler|sentry|datadog|"
                         r"logstash|cloudwatch", text, re.I)
    assert not re.search(r"[\"'](logs|error_logs|app_logs)[\"']", text)
