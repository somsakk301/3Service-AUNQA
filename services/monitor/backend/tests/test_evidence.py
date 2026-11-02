"""Evidence (SET 3): the monitored curriculum's source documents, read as stored.

`documents.curriculumId -> curricula._id` (Data Dictionary) is the only relationship used; every PS result
of the curriculum carries the same documents (project owner, 2026-09-26). Each item is
{label: fileName, reference: documents._id, storage: originalFile.storage, path: originalFile.path};
a value the document lacks is None, never made up. Evidence is read only and changes no result.
"""
import copy
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_service
from app.main import create_app
from app.repositories.base import DataSourceError
from app.repositories.configuration import ConfigurationRepository
from app.repositories.source_data import SourceDataRepository
from app.services.monitoring_service import MonitoringService
from tests.support.fixtures import GENERATION_READINESS, base_data, make_service, oid
from tests.support.memory_store import InMemoryConfigurationAdapter, InMemorySourceAdapter

APP_DIR = Path(__file__).resolve().parents[1] / "app"
CODES = [f"PS-0{n}" for n in range(1, 10)]


def document(curriculum_id, name="TEST-curriculum.pdf", original="default", **extra):
    """TEST-ONLY documents record shaped by the Data Dictionary (documents)."""
    doc = {"_id": oid(), "documentType": "curriculum", "fileType": "pdf", "fileName": name, "curriculumId": curriculum_id,
           "status": "processed", **extra}
    if original == "default":
        original = {"storage": "local", "path": f"test-data/documents/original/curriculum/{name}"}
    if original is not None:
        doc["originalFile"] = original
    return doc


def with_documents(data, *docs):
    data.setdefault("documents", []).extend(docs)
    return data


def cid(data):
    return data["curricula"][0]["_id"]


def monitor(data, **kw):
    return make_service(data, **kw)[0].monitor()


def evidence_json(resp):
    """The evidence of every result, as the API sends it."""
    return {r["psCode"]: r["evidence"] for r in resp.model_dump(by_alias=True)["results"]}


def client_for(service):
    app = create_app()
    app.dependency_overrides[get_service] = lambda: service
    return TestClient(app)


# --- TEST 01 .. 06 ------------------------------------------------------------------------------------
def test_01_a_document_with_storage_and_path_is_evidence_of_every_ps_of_its_curriculum(data):
    d = document(cid(data))
    ev = evidence_json(monitor(with_documents(data, d)))
    expected = [{"label": "TEST-curriculum.pdf", "reference": str(d["_id"]), "storage": "local",
                 "path": "test-data/documents/original/curriculum/TEST-curriculum.pdf"}]
    assert list(ev) == CODES and all(items == expected for items in ev.values())


def test_02_a_document_without_original_file_has_no_storage_or_path(data):
    d = document(cid(data), original=None)
    items = monitor(with_documents(data, d)).results[0].evidence
    assert [(i.label, i.reference, i.storage, i.path) for i in items] == [("TEST-curriculum.pdf", str(d["_id"]), None, None)]


@pytest.mark.parametrize("original, storage, path", [
    ({"path": "test-data/x.pdf"}, None, "test-data/x.pdf"),                 # TEST 03: no storage
    ({"storage": "local"}, "local", None),                                  # TEST 04: no path
    ({"storage": "  ", "path": ""}, None, None),                            # blank is not a value
    ({"storage": 1, "path": ["test-data/x.pdf"]}, None, None),              # not text: never converted
    ("test-data/x.pdf", None, None),                                        # originalFile not an object
])
def test_03_04_a_missing_storage_or_path_stays_missing(data, original, storage, path):
    item = monitor(with_documents(data, document(cid(data), original=original))).results[0].evidence[0]
    assert (item.storage, item.path) == (storage, path)


def test_a_document_without_file_name_is_labelled_by_its_reference(data):
    d = document(cid(data))
    del d["fileName"]
    item = monitor(with_documents(data, d)).results[0].evidence[0]
    assert item.label == item.reference == str(d["_id"])


def test_05_no_document_of_the_curriculum_gives_no_evidence(data):
    assert all(r.evidence == [] for r in monitor(data).results)                          # no documents at all
    with_documents(data, document(oid()), document(None))                               # other / no curriculum
    assert all(r.evidence == [] for r in monitor(data).results)


def test_06_several_documents_each_once_in_source_order(data):
    docs = [document(cid(data), name=f"TEST-{n}.pdf") for n in range(3)]
    with_documents(data, *docs, document(oid(), name="TEST-other.pdf"))
    for r in monitor(data).results:
        assert [i.reference for i in r.evidence] == [str(d["_id"]) for d in docs]


def test_06_a_document_returned_twice_by_the_source_is_listed_once(data):
    d = document(cid(data))
    with_documents(data, d, copy.deepcopy(d))
    assert [len(r.evidence) for r in monitor(data).results] == [1] * 9


# --- TEST 07 / 08: API ------------------------------------------------------------------------------
def test_07_api_monitor_sends_the_evidence(data):
    d = document(cid(data))
    body = client_for(make_service(with_documents(data, d))[0]).get("/api/monitor").json()
    assert all(r["evidence"] == [{"label": "TEST-curriculum.pdf", "reference": str(d["_id"]), "storage": "local",
                                  "path": "test-data/documents/original/curriculum/TEST-curriculum.pdf"}]
               for r in body["results"])


@pytest.mark.parametrize("code", CODES)
def test_08_api_ps_detail_sends_the_same_evidence(data, code):
    with_documents(data, document(cid(data)), document(cid(data), name="TEST-2.pdf", original=None))
    c = client_for(make_service(data)[0])
    listed = next(r for r in c.get("/api/monitor").json()["results"] if r["psCode"] == code)
    assert c.get(f"/api/monitor/ps/{code}").json()["evidence"] == listed["evidence"]


def test_a_document_read_failure_is_503_not_fail(data):
    class DocumentsUnreadable(InMemorySourceAdapter):
        def find(self, collection, query):
            if collection == "documents":
                raise DataSourceError("connection refused")
            return super().find(collection, query)

    service = MonitoringService(ConfigurationRepository(InMemoryConfigurationAdapter(data["ps_requirements"])),
                                SourceDataRepository(DocumentsUnreadable(data)))
    for path in ("/api/monitor", "/api/monitor/ps/PS-01"):
        r = client_for(service).get(path)
        assert r.status_code == 503 and r.json() == {"detail": "Unable to load monitoring data"} and "FAIL" not in r.text


# --- read only; evidence changes no result ------------------------------------------------------------
def test_documents_are_read_only_and_by_curriculum(data):
    with_documents(data, document(cid(data)), document(cid(data), original=None))
    before = copy.deepcopy(data)
    service, source = make_service(data)
    service.monitor()
    assert data == before and {op for op, _ in source.calls} == {"find"}
    assert ("find", "documents") in source.calls


def test_evidence_is_not_traceability(data):
    with_documents(data, document(cid(data)))
    for r in monitor(data).results:
        assert "documents" not in {t.collection for t in r.traceability}
        assert r.verification.found == len(r.traceability)


def scenario_base(d): ...


def scenario_fail_and_missing_year(d):
    d["appointments"].remove(next(a for a in d["appointments"] if a["role"] == "programmeResponsible"))
    del d["curricula"][0]["curriculumYear"]


@pytest.mark.parametrize("mutate", [scenario_base, scenario_fail_and_missing_year])
def test_11_12_evidence_changes_no_result_nor_readiness(mutate):
    """TEST 11 (Programme Readiness) and TEST 12 (Generation Readiness): documents added or removed change
    nothing but `evidence`."""
    without = base_data()
    mutate(without)
    without["ps_requirements"].append(copy.deepcopy(GENERATION_READINESS))
    with_docs = with_documents(copy.deepcopy(without), document(cid(without)),
                               document(cid(without), name="TEST-2.pdf", original=None))
    a, b = monitor(with_docs), monitor(without)
    assert a.programme_readiness == b.programme_readiness
    assert a.generation_readiness == b.generation_readiness
    strip = {"results": {"__all__": {"evidence"}}}
    assert a.model_dump(exclude=strip) == b.model_dump(exclude=strip)
    assert all(len(r.evidence) == 2 for r in a.results) and all(r.evidence == [] for r in b.results)


def test_no_evidence_value_is_written_into_application_source():
    for path in APP_DIR.rglob("*.py"):
        text = path.read_text()
        assert not re.search(r"project-data|\.pdf|\.docx?\b|มคอ", text), path
