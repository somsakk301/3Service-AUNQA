"""TEST-ONLY fixtures.

* PS configuration: verbatim copy of the authoritative PS Config (see fixtures/PROVENANCE.md).
* Generation readiness: the configuration document the project owner defined for `ps_requirements`
  (see fixtures/PROVENANCE.md). Not part of base_data(): a test adds it to `ps_requirements` itself.
* Source data: shaped by the Data Dictionary (educations.degree / .field, appointments.role, ...).
"""
import copy
import json
from pathlib import Path

from bson import ObjectId

from app.monitoring.helpers import SpecGap
from app.repositories.configuration import ConfigurationRepository
from app.repositories.source_data import SourceDataRepository
from app.services.monitoring_service import MonitoringService
from tests.support.memory_store import InMemoryConfigurationAdapter, InMemorySourceAdapter

AUTHORITATIVE_CONFIG = json.loads((Path(__file__).parent.parent / "fixtures" / "ps_config_v1.json").read_text())
GENERATION_READINESS = json.loads(
    (Path(__file__).parent.parent / "fixtures" / "generation_readiness_v1.json").read_text())

# The specification defines no reference values (e.g. the calendar of a year), so production
# resolves none. To exercise the configured arithmetic, tests inject values in the same
# calendar as the fixture data (curriculumYear 2567, ...).
TEST_CLOCK_YEAR = 2569


class FixedReferences:
    def __init__(self, values: dict[str, int], anchor: str = "currentYear") -> None:
        self._values = values
        self._anchor = anchor

    def resolve(self, name: str) -> int:
        if name not in self._values:
            raise SpecGap(f"reference '{name}' has no definition in the specification")
        return self._values[name]

    def period_anchor(self) -> int:
        return self.resolve(self._anchor)

    def in_anchor_calendar(self, year: int) -> int:
        return year          # fixed values carry no calendar: stored years are compared as they are


CURRICULUM_NAME = "วิทยาศาสตรบัณฑิต สาขาวิชาวิทยาการคอมพิวเตอร์"


def oid() -> ObjectId:
    return ObjectId()


def appointment(curriculum_id, person_id, role, role_name=None, **extra):
    return {
        "_id": oid(), "curriculumId": curriculum_id, "personId": person_id, "role": role,
        "roleName": role_name or role, "effectiveDate": "2567-11-13",
        "appointmentOrder": {"orderNumber": "350/2568", "orderDate": "2568-02-04"},
        "status": "active", **extra,
    }


def base_data():
    cid = oid()
    people = [oid() for _ in range(5)]
    appts = []
    for p in people:
        appts.append(appointment(cid, p, "programmeResponsible", "อาจารย์ผู้รับผิดชอบหลักสูตร"))
        appts.append(appointment(cid, p, "programmeStaff", "อาจารย์ประจำหลักสูตร"))
    return {
        "curricula": [{"_id": cid, "curriculumCode": "25500231104894", "curriculumName": CURRICULUM_NAME,
                       "curriculumYear": 2567, "version": 1, "status": "latest"}],
        "persons": [{"_id": p, "fullName": "x"} for p in people],
        "educations": [{"_id": oid(), "personId": p, "degree": "master", "field": "Computer Science",
                        "institution": "x", "graduationYear": 2555} for p in people],
        "appointments": appts,
        "academic_works": [{"_id": oid(), "personId": p, "workType": "journalArticle", "publicationYear": 2569}
                           for p in people],
        "ps_requirements": copy.deepcopy(AUTHORITATIVE_CONFIG),
    }


def make_service(data=None, year=TEST_CLOCK_YEAR, *, leak_inactive=False, references="default", manual=None,
                 results=None):
    """Service over in-memory adapters. `year=None` gives the production behaviour (no reference defined).
    `results`: a MonitoringResultRepository (Monitor-owned store); None = no store, verification stays null."""
    data = data if data is not None else base_data()
    source = InMemorySourceAdapter(data)
    config = InMemoryConfigurationAdapter(data["ps_requirements"] if "ps_requirements" in data else [], leak_inactive)
    if references == "default":
        references = FixedReferences({"currentYear": year}) if year is not None else None
    service = MonitoringService(ConfigurationRepository(config), SourceDataRepository(source), references, manual,
                                results=results)
    return service, source


def results(data=None, year=TEST_CLOCK_YEAR, **kw):
    service, _ = make_service(data, year, **kw)
    return {r.ps_code: r for r in service.monitor().results}


class ManualResults:
    """TEST-ONLY manual review results, keyed as the engine asks for them."""

    def __init__(self, values: dict[str, str]) -> None:
        self._values = values

    def get(self, key: str):
        return self._values.get(key)


def add_person(data, role, *, degree="master", field="Computer Science", works=(), institution="x"):
    """A person appointed with `role` in the monitored curriculum, with optional education and works."""
    pid, cid = oid(), data["curricula"][0]["_id"]
    data["persons"].append({"_id": pid, "fullName": "y"})
    data["appointments"].append(appointment(cid, pid, role))
    if degree is not None or field is not None:
        data["educations"].append({"_id": oid(), "personId": pid, "degree": degree, "field": field, "institution": institution})
    data["academic_works"] += [{"_id": oid(), "personId": pid, "workType": "journalArticle", "publicationYear": y} for y in works]
    return pid
