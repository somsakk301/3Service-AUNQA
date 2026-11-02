"""Seed a PRESERVED test dataset for the backend + Rule Engine (PS-01 ... PS-09).

TEST DATA ONLY. It writes to a separate test database (default `mornitor_backend_test`), never to the
source database the backend reads (MORNITOR_DB_NAME, default `mornitor_source`).

* Insert only: it never updates, replaces, drops or deletes anything, and has no cleanup step.
* Idempotent: every record has a fixed _id, so a record that is already there is skipped
  ("Test Data already exists"); nothing is duplicated.
* Every field is checked against the Data Schema (app/models/source_schema.py) before any write.
* `ps_requirements` is the project's PS Config (tests/fixtures/ps_config_v1.json), copied unchanged, plus
  the generation readiness document (tests/fixtures/generation_readiness_v1.json, told apart by
  `configType`). It is validated before any write, and a second document of that configType with
  another _id stops the script (no duplicate configuration).
* No PS result is stored: results come only from the backend (MongoDB -> Rule Engine -> API).

The Data Schema has no marker field (source / environment / testData ...), so test records are told
apart by their values: curricula.curriculumCode "TEST-...", persons P001 ... P008 (persons.lastName and
fullName), and every _id starts with 7e57da7a ("test data").

Run from backend/:
    .venv/bin/python scripts/seed_test_data.py            # insert what is missing
    .venv/bin/python scripts/seed_test_data.py --dry-run  # check only, write nothing
Target: MORNITOR_TEST_DB_URI (default mongodb://localhost:27017)
        MORNITOR_TEST_DB_NAME (default mornitor_backend_test; must end in "_test")
Then:   MORNITOR_DB_NAME=mornitor_backend_test .venv/bin/uvicorn app.main:app --port 8001
        GET /api/monitor?curriculumCode=TEST-IS-001
"""
import argparse
import copy
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from bson import ObjectId
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from app.models.source_schema import declared_type  # noqa: E402
from app.repositories.configuration import CONFIG_TYPE_KEY  # noqa: E402
from app.services.generation_readiness import ReadinessConfigProblem, validate  # noqa: E402

PS_CONFIG_FILE = BACKEND / "tests" / "fixtures" / "ps_config_v1.json"
GENERATION_READINESS_FILE = BACKEND / "tests" / "fixtures" / "generation_readiness_v1.json"
CONFIG_COLLECTION = "ps_requirements"
TEST_DB_NAME = re.compile(r"[A-Za-z0-9_]+_test")
SOURCE_DB_DEFAULT = "mornitor_source"  # app/settings.py: the backend's source database by default
MONITOR_OWNED = "monitoring_results"   # app/adapters/monitoring_results.py: written by the backend, not by this script
STATUS = "PRESERVED FOR TESTING"

# -- fixed, readable ids: 7e57da7a | collection code | record number (decimal digits) -----------------
ID_PREFIX = "7e57da7a"
CODES = {"curricula": "01", "persons": "02", "appointments": "03", "educations": "04",
         "academic_works": "05", CONFIG_COLLECTION: "06", "documents": "07"}
LOWEST, HIGHEST = ObjectId(ID_PREFIX + "0" * 16), ObjectId(ID_PREFIX + "f" * 16)


def tid(collection: str, number: int) -> ObjectId:
    return ObjectId(f"{ID_PREFIX}{CODES[collection]}{number:014d}")


TIMESTAMP = datetime(2026, 9, 25)  # Data Schema `timestamp`; fixed so a re-run builds identical records

# -- the dataset -------------------------------------------------------------------------------------
# persons P001 ... P008; the Data Schema identifies a person by persons._id (ObjectId), not by "P001"
PERSONS = {f"P00{n}": tid("persons", n) for n in range(1, 9)}
# persons.hasTeachingExperience: set once the person's CV is processed, absent before (Import Service SRS §15).
# PS-08 reads it (experience.source). P008's CV is processed; P006, the other special instructor, not yet.
TEACHING_EXPERIENCE = {"P008": True}

# curriculum number, curriculumCode, curriculumName, curriculumYear (None = field absent), purpose
CURRICULA = [
    (1, "TEST-IS-001", "หลักสูตรทดสอบระบบสารสนเทศ", 2567, "main dataset: PS-01 ... PS-09"),
    (2, "TEST-IS-002", "หลักสูตรทดสอบระบบสารสนเทศ (หลักสูตรที่สอง)", 2567, "PS-03: P001 responsible for a second curriculum"),
    (3, "TEST-PS01-FAIL", "หลักสูตรทดสอบระบบสารสนเทศ กรณีอาจารย์ผู้รับผิดชอบไม่ครบ 5 คน", 2567, "PS-01: 4 responsible"),
    (4, "TEST-PS01-REVIEW", "หลักสูตรทดสอบระบบสารสนเทศ กรณีการแต่งตั้งไม่ระบุบุคคล", 2567, "PS-01: an appointment without personId"),
    (5, "TEST-PS02-FAIL", "หลักสูตรทดสอบระบบสารสนเทศ กรณีไม่มีอาจารย์ประจำหลักสูตร", 2567, "PS-02: no programmeStaff"),
    (6, "TEST-PS04-MISSING", "หลักสูตรทดสอบระบบสารสนเทศ กรณีคำสั่งแต่งตั้งไม่ครบ", 2567, "PS-04: roleName / appointmentOrder missing"),
    (7, "TEST-PS06-UNKNOWN", "หลักสูตรทดสอบระบบสารสนเทศ กรณีคุณวุฒิไม่ระบุสาขา", 2567, "PS-06: educations.field missing"),
    (8, "TEST-PS07-REVIEW", "หลักสูตรทดสอบระบบสารสนเทศ กรณีผลงานไม่ระบุปีที่ตีพิมพ์", 2567, "PS-07: publicationYear missing"),
    (9, "TEST-PS08-REVIEW", "หลักสูตรทดสอบระบบสารสนเทศ กรณีอาจารย์พิเศษไม่มีข้อมูลคุณวุฒิ", 2567, "PS-08: no education for the special instructor"),
    (10, "TEST-PS09-FAIL", "หลักสูตรทดสอบระบบสารสนเทศ กรณีปรับปรุงนานเกิน 5 ปี", 2560, "PS-09: curriculumYear 2560"),
    (11, "TEST-PS09-MISSING", "หลักสูตรทดสอบระบบสารสนเทศ กรณีไม่ระบุปีของหลักสูตร", None, "PS-09: curriculumYear missing"),
]
CURRICULUM_ID = {code: tid("curricula", n) for n, code, *_ in CURRICULA}

RESPONSIBLE = ("programmeResponsible", "อาจารย์ผู้รับผิดชอบหลักสูตร")
STAFF = ("programmeStaff", "อาจารย์ประจำหลักสูตร")
SPECIAL = ("specialInstructor", "อาจารย์พิเศษ")
FULL_ORDER = "full"  # appointmentOrder with orderNumber and orderDate

# appointment number, curriculumCode, person (None = personId absent), (role, roleName or None), order
APPOINTMENTS = [
    *[(100 + i, "TEST-IS-001", f"P00{i}", RESPONSIBLE, FULL_ORDER) for i in range(1, 6)],
    *[(105 + i, "TEST-IS-001", f"P00{i}", STAFF, FULL_ORDER) for i in range(1, 6)],
    (111, "TEST-IS-001", "P008", SPECIAL, FULL_ORDER),
    (201, "TEST-IS-002", "P001", RESPONSIBLE, FULL_ORDER),
    *[(300 + i, "TEST-PS01-FAIL", f"P00{i}", RESPONSIBLE, FULL_ORDER) for i in range(1, 5)],
    *[(304 + i, "TEST-PS01-FAIL", f"P00{i}", STAFF, FULL_ORDER) for i in range(1, 5)],
    *[(400 + i, "TEST-PS01-REVIEW", f"P00{i}", RESPONSIBLE, FULL_ORDER) for i in range(1, 6)],
    *[(405 + i, "TEST-PS01-REVIEW", f"P00{i}", STAFF, FULL_ORDER) for i in range(1, 6)],
    (411, "TEST-PS01-REVIEW", None, RESPONSIBLE, FULL_ORDER),
    *[(500 + i, "TEST-PS02-FAIL", f"P00{i}", RESPONSIBLE, FULL_ORDER) for i in range(1, 6)],
    (601, "TEST-PS04-MISSING", "P001", RESPONSIBLE, FULL_ORDER),
    (602, "TEST-PS04-MISSING", "P006", (RESPONSIBLE[0], None), None),   # no roleName, no appointmentOrder
    (603, "TEST-PS04-MISSING", "P007", RESPONSIBLE, "number only"),     # appointmentOrder without orderDate
    (701, "TEST-PS06-UNKNOWN", "P007", RESPONSIBLE, FULL_ORDER),
    (801, "TEST-PS07-REVIEW", "P004", RESPONSIBLE, FULL_ORDER),
    (901, "TEST-PS08-REVIEW", "P006", SPECIAL, FULL_ORDER),
]

# education number, person, degree, field (None = field absent)
# degree is a free String in the Data Schema. "master" is the configuration's value (PS-05 degree.minimum),
# "Ph.D." the Data Schema's own example; the code and schema give no bachelor value, so "bachelor" follows
# the configuration's spelling. P006 has no education (PS-05 / PS-08 missing qualification).
EDUCATIONS = [
    (11, "P001", "master", "Information Science"),
    (21, "P002", "Ph.D.", "Computer Science"),
    (31, "P003", "bachelor", "Information Science"),
    (41, "P004", "master", "Information Systems"),
    (51, "P005", "master", "Accounting"),
    (71, "P007", "master", None),
    (81, "P008", "master", "Information Technology"),
]

# work number, person, workType, title, publicationYear (None = field absent), database
# P003, P006, P007 and P008 have no academic work.
WORKS = [
    (11, "P001", "journalArticle", "งานวิจัยทดสอบของ P001", 2566, "Scopus"),
    (21, "P002", "journalArticle", "งานวิจัยทดสอบของ P002", 2568, "TCI"),
    (22, "P002", "journalArticle", "งานวิจัยทดสอบของ P002 (ก่อนช่วง 5 ปี)", 2550, "TCI"),
    (41, "P004", "journalArticle", "งานวิจัยทดสอบของ P004 (ไม่ระบุปี)", None, "TCI"),
    (51, "P005", "conferencePaper", "งานวิจัยทดสอบของ P005", 2567, "Scopus"),
]

# document number, curriculumCode, documentType, fileName, originalFile (None = field absent)
# Evidence: the Data Dictionary's relative local path; TEST-... file names (no real file exists).
DOCUMENTS = [
    (1, "TEST-IS-001", "curriculum", "TEST-IS-001-curriculum.pdf",
     {"storage": "local", "path": "project-data/documents/original/curriculum/TEST-IS-001-curriculum.pdf"}),
    (2, "TEST-IS-001", "appointment", "TEST-IS-001-appointment.pdf", None),       # no originalFile
    (3, "TEST-IS-001", "cv", "TEST-P001-cv.pdf", {"storage": "local"}),           # originalFile without path
    (4, "TEST-IS-002", "curriculum", "TEST-IS-002-curriculum.pdf",
     {"storage": "local", "path": "project-data/documents/original/curriculum/TEST-IS-002-curriculum.pdf"}),
]


def build() -> dict[str, list[dict]]:
    """Every record to seed, in Data Schema shape (Buddhist-era years and date strings, as its examples)."""
    data: dict[str, list[dict]] = {c: [] for c in CODES}
    for n, code, name, year, _ in CURRICULA:
        doc = {"_id": tid("curricula", n), "curriculumCode": code, "curriculumName": name}
        if year is not None:
            doc["curriculumYear"] = year
        data["curricula"].append({**doc, "version": 1, "status": "latest", "timestamp": TIMESTAMP})
    for key, pid in PERSONS.items():
        first = "ทดสอบพิเศษ" if key == "P008" else "ทดสอบ"
        doc = {"_id": pid, "title": "อ.", "firstName": first, "lastName": key, "fullName": f"อ.{first} {key}",
               "academicPosition": "อาจารย์"}
        if key in TEACHING_EXPERIENCE:
            doc["hasTeachingExperience"] = TEACHING_EXPERIENCE[key]
        data["persons"].append({**doc, "timestamp": TIMESTAMP})
    for n, code, person, (role, role_name), order in APPOINTMENTS:
        doc = {"_id": tid("appointments", n), "curriculumId": CURRICULUM_ID[code]}
        if person is not None:
            doc["personId"] = PERSONS[person]
        doc["role"] = role
        if role_name is not None:
            doc["roleName"] = role_name
        doc["effectiveDate"] = "2567-11-13"
        if order is not None:
            doc["appointmentOrder"] = {"orderNumber": f"TEST-{n}/2567"}
            if order == FULL_ORDER:
                doc["appointmentOrder"]["orderDate"] = "2567-10-01"
        data["appointments"].append({**doc, "status": "active", "timestamp": TIMESTAMP})
    for n, person, degree, field in EDUCATIONS:
        doc = {"_id": tid("educations", n), "personId": PERSONS[person], "degree": degree}
        if field is not None:
            doc["field"] = field
        data["educations"].append({**doc, "institution": "มหาวิทยาลัยทดสอบ", "graduationYear": 2555, "timestamp": TIMESTAMP})
    for n, person, work_type, title, year, database in WORKS:
        doc = {"_id": tid("academic_works", n), "personId": PERSONS[person], "workType": work_type, "title": title}
        if year is not None:
            doc["publicationYear"] = year
        data["academic_works"].append({**doc, "database": database, "timestamp": TIMESTAMP})
    for n, code, document_type, file_name, original in DOCUMENTS:
        doc = {"_id": tid("documents", n), "documentType": document_type, "fileType": "pdf", "fileName": file_name,
               "curriculumId": CURRICULUM_ID[code]}
        if original is not None:
            doc["originalFile"] = dict(original)
        data["documents"].append({**doc, "status": "processed", "timestamp": TIMESTAMP})   # the Data Schema's example
    config = json.loads(PS_CONFIG_FILE.read_text(encoding="utf-8"))
    readiness = json.loads(GENERATION_READINESS_FILE.read_text(encoding="utf-8"))
    data[CONFIG_COLLECTION] = [{"_id": tid(CONFIG_COLLECTION, n), **copy.deepcopy(doc)}
                               for n, doc in enumerate([*config, readiness], start=1)]
    return data


def config_type_documents(data: dict[str, list[dict]]) -> list[dict]:
    return [d for d in data[CONFIG_COLLECTION] if CONFIG_TYPE_KEY in d]


def configuration_problems(data: dict[str, list[dict]]) -> list[str]:
    """The generation readiness document must be one the backend accepts, checked as the backend checks it."""
    problems = []
    for doc in config_type_documents(data):
        try:
            validate(doc)
        except ReadinessConfigProblem as problem:
            problems.append(f"{GENERATION_READINESS_FILE.name}: {problem.issue}: {problem.detail}")
    return problems


def duplicate_problems(db, data: dict[str, list[dict]]) -> list[str]:
    """A document of the same configType under another _id would make the backend's configuration ambiguous."""
    problems = []
    for doc in config_type_documents(data):
        query = {CONFIG_TYPE_KEY: doc[CONFIG_TYPE_KEY], "_id": {"$ne": doc["_id"]}}
        for other in db[CONFIG_COLLECTION].find(query, {"_id": 1}):
            problems.append(f"{CONFIG_COLLECTION} {other['_id']}: another {CONFIG_TYPE_KEY} "
                            f"{doc[CONFIG_TYPE_KEY]!r} document (this script's is {doc['_id']})")
    return problems


# -- checks before any write -----------------------------------------------------------------------
_TYPES = {"ObjectId": ObjectId, "String": str, "Integer": int, "Boolean": bool, "Object": dict,
          "Date": datetime, "Date/String": (datetime, str)}


def schema_problems(data: dict[str, list[dict]]) -> list[str]:
    """Every field must be declared by the Data Schema, with its declared type. No field is invented."""
    problems = []

    def walk(collection, doc, prefix=""):
        for key, value in doc.items():
            path = prefix + key
            declared = declared_type(collection, path)
            if declared is None:
                problems.append(f"{collection}.{path}: not declared by the Data Schema")
                continue
            ok = isinstance(value, _TYPES[declared]) and not (declared == "Integer" and isinstance(value, bool))
            if not ok:
                problems.append(f"{collection}.{path}: {type(value).__name__}, the Data Schema declares {declared}")
            if isinstance(value, dict):
                walk(collection, value, path + ".")

    for collection, docs in data.items():
        if collection == CONFIG_COLLECTION:
            continue          # configuration, not source data: copied as is from the project's PS Config
        for doc in docs:
            walk(collection, doc)
    return problems


def target_problems(db_name: str) -> list[str]:
    """Checked before every write: the target must be a test database, never the backend's source."""
    problems = []
    if db_name == SOURCE_DB_DEFAULT:
        problems.append(f"database '{db_name}' is the backend's source database")
    if not TEST_DB_NAME.fullmatch(db_name):
        problems.append(f"database '{db_name}' is not a test database (its name must end in _test)")
    return problems


def content_problems(db) -> list[str]:
    """An existing database may hold this script's test records only; anything else may be real data.
    `monitoring_results` is the backend's own store (verifications made while testing): never written or
    checked here."""
    problems = []
    for name in sorted(db.list_collection_names()):
        if name == MONITOR_OWNED:
            continue
        if name not in CODES:
            problems.append(f"collection '{name}' is not part of the test dataset")
            continue
        other = db[name].count_documents({"_id": {"$not": {"$gte": LOWEST, "$lte": HIGHEST}}})
        if other:
            problems.append(f"{name}: {other} record(s) that are not test data (_id not starting with {ID_PREFIX})")
    return problems


def stop(title: str, problems: list[str]) -> None:
    print(f"STOP: {title}")
    for p in problems:
        print(f"  - {p}")
    print("Stopped: nothing (more) was written.")
    sys.exit(1)


# -- main --------------------------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Insert the preserved backend test dataset (no delete, no update).")
    parser.add_argument("--dry-run", action="store_true", help="check everything, write nothing")
    args = parser.parse_args()

    uri = os.environ.get("MORNITOR_TEST_DB_URI", "mongodb://localhost:27017")
    db_name = os.environ.get("MORNITOR_TEST_DB_NAME", "mornitor_backend_test")
    print(f"Mongo URI:   {uri}")
    print(f"Database:    {db_name}")
    print(f"Environment: TEST (a separate test database; {SOURCE_DB_DEFAULT} and every other database are not touched)")

    if problems := target_problems(db_name):
        stop("the target is not a test database", problems)
    data = build()
    if problems := schema_problems(data):
        stop("the dataset does not match the Data Schema", problems)
    if problems := configuration_problems(data):
        stop("the generation readiness configuration is not valid", problems)

    client = MongoClient(uri, serverSelectionTimeoutMS=3000)
    db = client[db_name]
    existed = db_name in client.list_database_names()
    print(f"Database exists: {'yes' if existed else 'no (created by the first insert)'}")
    print(f"Collections: {', '.join(sorted(db.list_collection_names())) or '(none)'}")
    if problems := content_problems(db):
        stop("the database holds data that is not this test dataset", problems)
    if problems := duplicate_problems(db, data):
        stop("the database already holds another generation readiness configuration", problems)

    inserted = {c: 0 for c in data}
    present = {c: 0 for c in data}
    differs: list[str] = []
    for collection, docs in data.items():
        for doc in docs:
            found = db[collection].find_one({"_id": doc["_id"]})
            if found is not None:
                present[collection] += 1
                if found != doc:
                    differs.append(f"{collection} {doc['_id']}")
                continue
            if args.dry_run:
                inserted[collection] += 1
                continue
            if problems := target_problems(db.name):   # before every write: the database actually written to
                stop("the target is not a test database", problems)
            try:
                db[collection].insert_one(doc)
                inserted[collection] += 1
            except DuplicateKeyError:
                present[collection] += 1

    total_new = sum(inserted.values())
    print()
    if args.dry_run:
        print(f"DRY RUN: {total_new} record(s) would be inserted; nothing was written")
    elif total_new == 0:
        print("Test Data already exists")
    else:
        print("TEST DATA INSERTED")
    print(f"\nDatabase:\n{db_name}")
    print("\nCurriculum:")
    for n, code, _, year, purpose in CURRICULA:
        print(f"{code:<18} curriculumYear={year if year is not None else '(absent)':<9} _id={tid('curricula', n)}  {purpose}")
    print("\nPersons (test id -> persons._id):")
    for key, pid in PERSONS.items():
        print(f"{key} -> {pid}")
    labels = {"persons": "Persons", "curricula": "Curricula", "appointments": "Appointments", "educations": "Educations",
              "academic_works": "Academic Works", "documents": "Documents",
              CONFIG_COLLECTION: "PS Requirements (project PS Config + generation readiness document, unchanged)"}
    new = "would insert" if args.dry_run else "inserted now"
    print()
    for collection in ("curricula", "persons", "appointments", "educations", "academic_works", "documents",
                       CONFIG_COLLECTION):
        print(f"{labels[collection]}:\n{len(data[collection])} "
              f"({new}: {inserted[collection]}, already present: {present[collection]})")
    if differs:
        print("\nAlready present but different from this script (left unchanged, never overwritten):")
        for d in differs:
            print(f"  - {d}")
        print("To test the current records, seed a new test database: MORNITOR_TEST_DB_NAME=<name>_test")
    print(f"\nStatus:\n{STATUS}")


if __name__ == "__main__":
    main()
