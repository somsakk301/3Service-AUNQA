"""Same configuration + same source data => same result, in-memory vs a real MongoDB.

Starts a throwaway `mongod` (temporary directory, random port) and loads TEST data into
it through pymongo. The application adapters under test only read. Skipped if `mongod`
is not installed. This proves adapter parity, not deployment against the Data Import DB.
"""
import copy
import shutil
import socket
import subprocess
import time
from datetime import datetime

import pytest
from pymongo import MongoClient, monitoring

from app.adapters.mongo import MongoConfigurationAdapter, MongoSourceDataAdapter
from app.repositories.configuration import ConfigurationRepository
from app.repositories.source_data import SourceDataRepository
from app.models.status import Readiness, Status
from app.services.monitoring_service import MonitoringService
from tests.support.fixtures import (
    GENERATION_READINESS, TEST_CLOCK_YEAR, FixedReferences, appointment, base_data, make_service, oid,
)

pytestmark = pytest.mark.skipif(shutil.which("mongod") is None, reason="mongod not installed")

SOURCE = ["curricula", "persons", "educations", "appointments", "academic_works", "documents", "data_usages",
          "generated_documents"]


class CommandLog(monitoring.CommandListener):
    def __init__(self):
        self.names: list[str] = []

    def started(self, event):
        self.names.append(event.command_name)

    def succeeded(self, event): ...
    def failed(self, event): ...


@pytest.fixture(scope="module")
def mongo(tmp_path_factory):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    dbpath = tmp_path_factory.mktemp("mongod")
    proc = subprocess.Popen(["mongod", "--dbpath", str(dbpath), "--port", str(port), "--bind_ip", "127.0.0.1", "--nounixsocket"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    log = CommandLog()
    client = MongoClient(f"mongodb://127.0.0.1:{port}", serverSelectionTimeoutMS=500, event_listeners=[log])
    for _ in range(60):
        try:
            client.admin.command("ping")
            break
        except Exception:
            time.sleep(0.5)
    else:
        proc.terminate()
        pytest.skip("mongod did not start")
    yield client, log
    client.close()
    proc.terminate()
    proc.wait(timeout=20)


def load(client, data):
    """TEST SETUP ONLY: fill a scratch database standing in for the Data Import side."""
    client.drop_database("source")
    client.drop_database("config")
    for name in SOURCE:
        if data.get(name):
            client["source"][name].insert_many(copy.deepcopy(data[name]))
    client["config"]["ps_requirements"].insert_many(copy.deepcopy(data["ps_requirements"]))


def mongo_service(client):
    return MonitoringService(
        ConfigurationRepository(MongoConfigurationAdapter(client["config"])),
        SourceDataRepository(MongoSourceDataAdapter(client["source"])),
        FixedReferences({"currentYear": TEST_CLOCK_YEAR}),
    )


def scenario_base(d): ...


def scenario_few_responsible(d):
    d["appointments"].remove(next(a for a in d["appointments"] if a["role"] == "programmeResponsible"))


def scenario_other_degree_and_missing_order(d):
    d["educations"][0]["degree"] = "Ph.D."
    del d["appointments"][0]["appointmentOrder"]["orderNumber"]


def scenario_special_instructor_and_other_curriculum(d):
    pid = oid()
    d["appointments"].append(appointment(d["curricula"][0]["_id"], pid, "specialInstructor"))
    d["educations"].append({"_id": oid(), "personId": pid, "degree": "master", "field": "x"})
    d["appointments"].append(appointment(oid(), oid(), "programmeResponsible"))


def scenario_unqualified_and_unrelated(d):
    cid = d["curricula"][0]["_id"]
    d["appointments"].append(appointment(cid, oid(), "specialInstructor"))                 # subject without any education
    for e in d["educations"][:3]:
        e.update(degree="Ph.D.", field="Biology")                                          # no ordering / unrelated field


def scenario_stale_works_and_missing_staff(d):
    for w in d["academic_works"][:2]:
        w["publicationYear"] = 2550                                                       # outside the window
    d["appointments"].remove(next(a for a in d["appointments"] if a["role"] == "programmeStaff"))
    d["educations"].pop()


def scenario_related_field_and_qualified_instructor(d):
    pid = oid()
    d["appointments"].append(appointment(d["curricula"][0]["_id"], pid, "specialInstructor"))
    d["educations"].append({"_id": oid(), "personId": pid, "degree": "master", "field": "x", "institution": "y"})
    d["educations"][0]["field"] = "Information Technology"                                # a related field


def scenario_inactive_configuration(d):
    d["ps_requirements"][4]["active"] = False


def scenario_missing_year(d):
    del d["curricula"][0]["curriculumYear"]


def scenario_generation_readiness_document(d):
    d["ps_requirements"].append(copy.deepcopy(GENERATION_READINESS))


def scenario_generation_readiness_and_few_responsible(d):
    scenario_generation_readiness_document(d)
    scenario_few_responsible(d)


def scenario_documents(d):
    """Evidence: documents of this curriculum (complete, no originalFile, no path) and of another one."""
    cid = d["curricula"][0]["_id"]
    base = {"documentType": "curriculum", "fileType": "pdf", "status": "processed"}
    d["documents"] = [
        {"_id": oid(), **base, "fileName": "TEST-1.pdf", "curriculumId": cid,
         "originalFile": {"storage": "local", "path": "test-data/documents/original/curriculum/TEST-1.pdf"}},
        {"_id": oid(), **base, "fileName": "TEST-2.pdf", "curriculumId": cid},
        {"_id": oid(), **base, "fileName": "TEST-3.pdf", "curriculumId": cid, "originalFile": {"storage": "local"}},
        {"_id": oid(), **base, "fileName": "TEST-other.pdf", "curriculumId": oid(),
         "originalFile": {"storage": "local", "path": "test-data/documents/original/curriculum/TEST-other.pdf"}},
    ]


@pytest.mark.parametrize("mutate", [scenario_base, scenario_few_responsible, scenario_other_degree_and_missing_order,
                                    scenario_special_instructor_and_other_curriculum, scenario_unqualified_and_unrelated,
                                    scenario_stale_works_and_missing_staff, scenario_related_field_and_qualified_instructor,
                                    scenario_inactive_configuration,
                                    scenario_missing_year, scenario_generation_readiness_document,
                                    scenario_generation_readiness_and_few_responsible, scenario_documents])
def test_same_configuration_and_data_give_the_same_result(mongo, mutate):
    client, log = mongo
    data = base_data()
    mutate(data)
    load(client, data)

    expected = make_service(copy.deepcopy(data))[0].monitor().model_dump(by_alias=True)
    log.names.clear()
    actual = mongo_service(client).monitor().model_dump(by_alias=True)
    commands = list(log.names)

    assert actual == expected
    assert commands and set(commands) <= {"find", "getMore", "killCursors", "endSessions"}, commands


def test_single_ps_detail_matches_and_only_reads(mongo):
    client, log = mongo
    data = base_data()
    load(client, data)
    expected = make_service(copy.deepcopy(data))[0].ps_detail("PS-05")
    log.names.clear()
    actual = mongo_service(client).ps_detail("PS-05")
    assert actual == expected and set(log.names) <= {"find", "getMore", "killCursors", "endSessions"}


def test_mongo_source_data_is_unchanged_by_a_run(mongo):
    client, _ = mongo
    data = base_data()
    load(client, data)
    snapshot = {n: list(client["source"][n].find()) for n in SOURCE}
    config_snapshot = list(client["config"]["ps_requirements"].find())
    mongo_service(client).monitor()
    assert {n: list(client["source"][n].find()) for n in SOURCE} == snapshot
    assert list(client["config"]["ps_requirements"].find()) == config_snapshot


def test_generation_readiness_is_read_from_ps_requirements_in_mongodb_without_a_new_collection(mongo):
    client, log = mongo
    data = base_data()
    scenario_generation_readiness_document(data)
    load(client, data)
    assert client["config"].list_collection_names() == ["ps_requirements"]
    assert client["config"]["ps_requirements"].count_documents({"psCode": {"$exists": True}}) == 9
    assert client["config"]["ps_requirements"].count_documents({"configType": "generationReadiness"}) == 1
    snapshot = list(client["config"]["ps_requirements"].find())

    log.names.clear()
    resp = mongo_service(client).monitor()
    assert resp.generation_readiness.status is Readiness.NOT_READY
    assert [(b.ps_code, b.status) for b in resp.generation_readiness.blocking_ps] == [("PS-03", Status.REVIEW),
                                                                                    ("PS-06", Status.REVIEW)]
    assert [r.ps_code for r in resp.results] == [f"PS-0{n}" for n in range(1, 10)]
    assert set(log.names) <= {"find", "getMore", "killCursors", "endSessions"}
    assert client["config"].list_collection_names() == ["ps_requirements"]        # no collection created
    assert list(client["config"]["ps_requirements"].find()) == snapshot            # nothing written


def test_evidence_is_read_from_mongodb_documents_and_nothing_is_written(mongo):
    client, log = mongo
    data = base_data()
    scenario_documents(data)
    load(client, data)
    snapshot = list(client["source"]["documents"].find())
    log.names.clear()
    evidence = [[(e.label, e.storage, e.path) for e in r.evidence] for r in mongo_service(client).monitor().results]
    assert evidence == [[("TEST-1.pdf", "local", "test-data/documents/original/curriculum/TEST-1.pdf"),
                         ("TEST-2.pdf", None, None), ("TEST-3.pdf", "local", None)]] * 9
    assert set(log.names) <= {"find", "getMore", "killCursors", "endSessions"}
    assert list(client["source"]["documents"].find()) == snapshot


def test_verification_is_kept_in_monitoring_results_only(mongo):
    """SET 4 on a real mongod: the one written collection is `monitoring_results` (its own database here);
    one record per curriculumId + psCode, enforced by a unique index; source and configuration unchanged."""
    from app.adapters.monitoring_results import MongoMonitoringResultAdapter
    from app.repositories.monitoring_results import MonitoringResultRepository

    client, log = mongo
    data = base_data()
    scenario_documents(data)
    load(client, data)
    client.drop_database("results")                                   # TEST SETUP ONLY: a fresh Monitor store
    source_before = {n: list(client["source"][n].find()) for n in SOURCE}
    config_before = list(client["config"]["ps_requirements"].find())

    def service():
        return MonitoringService(ConfigurationRepository(MongoConfigurationAdapter(client["config"])),
                                 SourceDataRepository(MongoSourceDataAdapter(client["source"])),
                                 FixedReferences({"currentYear": TEST_CLOCK_YEAR}),
                                 results=MonitoringResultRepository(MongoMonitoringResultAdapter(client["results"])))

    before = service().monitor()
    assert {r.verification.verified for r in before.results} == {False}
    for _ in range(3):                                                # repeated clicks
        service().verify("PS-05")
    stored = list(client["results"]["monitoring_results"].find({}, {"_id": 0}))
    assert len(stored) == 1 and set(stored[0]) == {"curriculumId", "psCode", "verification"}
    assert (stored[0]["curriculumId"], stored[0]["psCode"]) == (data["curricula"][0]["_id"], "PS-05")
    assert stored[0]["verification"]["verified"] is True and isinstance(stored[0]["verification"]["verifiedAt"], datetime)
    index = client["results"]["monitoring_results"].index_information()["curriculumId_psCode"]
    assert index["unique"] is True and index["key"] == [("curriculumId", 1), ("psCode", 1)]

    log.names.clear()
    after = service().monitor()                                       # a fresh service: read back from MongoDB
    assert set(log.names) <= {"find", "getMore", "killCursors", "endSessions"}
    assert {r.ps_code for r in after.results if r.verification.verified} == {"PS-05"}
    ignore = {"results": {"__all__": {"verification": {"verified", "verified_at"}}}}
    assert after.model_dump(exclude=ignore) == before.model_dump(exclude=ignore)
    assert client["results"].list_collection_names() == ["monitoring_results"]
    assert {n: list(client["source"][n].find()) for n in SOURCE} == source_before
    assert list(client["config"]["ps_requirements"].find()) == config_before
    assert "monitoring_results" not in client["source"].list_collection_names() + client["config"].list_collection_names()


def test_ps03_review_shares_the_record_with_its_verification_in_monitoring_results(mongo):
    """SET 5 on a real mongod: the review is set in place in the curriculumId + psCode record, next to the
    verification; saving again updates it; the PS status stays the engine's; source and configuration unchanged."""
    from app.adapters.monitoring_results import MongoMonitoringResultAdapter
    from app.repositories.monitoring_results import MonitoringResultRepository

    client, log = mongo
    data = base_data()
    load(client, data)
    client.drop_database("results")                                   # TEST SETUP ONLY: a fresh Monitor store
    source_before = {n: list(client["source"][n].find()) for n in SOURCE}
    config_before = list(client["config"]["ps_requirements"].find())

    def service():
        return MonitoringService(ConfigurationRepository(MongoConfigurationAdapter(client["config"])),
                                 SourceDataRepository(MongoSourceDataAdapter(client["source"])),
                                 FixedReferences({"currentYear": TEST_CLOCK_YEAR}),
                                 results=MonitoringResultRepository(MongoMonitoringResultAdapter(client["results"])))

    service().review("PS-03", "PASS")
    service().verify("PS-03")
    service().review("PS-03", "FAIL")
    stored = list(client["results"]["monitoring_results"].find({}, {"_id": 0}))
    assert len(stored) == 1 and set(stored[0]) == {"curriculumId", "psCode", "verification", "review"}
    assert stored[0]["psCode"] == "PS-03" and stored[0]["review"]["status"] == "FAIL"
    assert stored[0]["verification"]["verified"] is True and isinstance(stored[0]["review"]["recordedAt"], datetime)

    log.names.clear()
    ps03 = next(r for r in service().monitor().results if r.ps_code == "PS-03")     # a fresh service
    assert set(log.names) <= {"find", "getMore", "killCursors", "endSessions"}
    assert (ps03.status, ps03.review.status, ps03.verification.verified) == (Status.REVIEW, Status.FAIL, True)
    assert {n: list(client["source"][n].find()) for n in SOURCE} == source_before
    assert list(client["config"]["ps_requirements"].find()) == config_before
    assert client["results"].list_collection_names() == ["monitoring_results"]


def test_persistent_monitoring_result_is_kept_in_monitoring_results_next_to_verification_and_review(mongo):
    """SET 6 on a real mongod: saving sets `result` in the curriculumId + psCode record of every active PS in one bulk
    write, keeps verification / review, replaces the result on the next save, and never touches source or config."""
    from app.adapters.monitoring_results import MongoMonitoringResultAdapter
    from app.repositories.monitoring_results import MonitoringResultRepository

    client, log = mongo
    data = base_data()
    scenario_documents(data)
    load(client, data)
    client.drop_database("results")                                   # TEST SETUP ONLY: a fresh Monitor store
    source_before = {n: list(client["source"][n].find()) for n in SOURCE}
    config_before = list(client["config"]["ps_requirements"].find())

    def service():
        return MonitoringService(ConfigurationRepository(MongoConfigurationAdapter(client["config"])),
                                 SourceDataRepository(MongoSourceDataAdapter(client["source"])),
                                 FixedReferences({"currentYear": TEST_CLOCK_YEAR}),
                                 results=MonitoringResultRepository(MongoMonitoringResultAdapter(client["results"])))

    service().verify("PS-03")
    service().review("PS-03", "PASS")
    current = service().monitor()
    service().save_results()
    service().save_results()                                          # saved again: same records, no duplicate
    stored = {d["psCode"]: d for d in client["results"]["monitoring_results"].find({}, {"_id": 0})}
    assert len(stored) == 9 and client["results"]["monitoring_results"].count_documents({}) == 9
    assert {c: d["result"]["status"] for c, d in stored.items()} == {r.ps_code: r.status.value for r in current.results}
    assert set(stored["PS-03"]) == {"curriculumId", "psCode", "verification", "review", "result"}
    assert (stored["PS-03"]["result"]["status"], stored["PS-03"]["review"]["status"]) == ("REVIEW", "PASS")

    log.names.clear()
    after = service().monitor()                                       # a fresh service: read back from MongoDB
    assert set(log.names) <= {"find", "getMore", "killCursors", "endSessions"}
    assert {r.ps_code: r.persisted_result.status for r in after.results} == {r.ps_code: r.status for r in current.results}
    ignore = {"results": {"__all__": {"persisted_result"}}}
    assert after.model_dump(exclude=ignore) == current.model_dump(exclude=ignore)
    assert {n: list(client["source"][n].find()) for n in SOURCE} == source_before
    assert list(client["config"]["ps_requirements"].find()) == config_before
    assert client["results"].list_collection_names() == ["monitoring_results"]
