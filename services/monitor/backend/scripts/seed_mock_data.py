"""Seed the MOCK-IS-001 dataset used to test the full Monitor flow against a real local MongoDB.

TEST / DEMO DATA ONLY. It writes to a separate mock database (default `mornitor_mock`), never to the
backend's real source database (MORNITOR_DB_NAME, default `mornitor_source`) or any database whose name
does not contain "mock".

* Insert only: it never updates, replaces, drops or deletes anything, and has no cleanup step.
* Idempotent: every record has a fixed _id, so a record that is already there is skipped
  ("Mock Data already exists"); nothing is duplicated.
* Every field is checked against the Data Schema (app/models/source_schema.py) before any write, exactly
  like backend/scripts/seed_test_data.py.
* `ps_requirements` is the project's PS Config (tests/fixtures/ps_config_v1.json), copied unchanged, plus
  the generation readiness document (tests/fixtures/generation_readiness_v1.json), told apart by
  `configType`. Neither file is modified by this script: the Rule Engine logic and PS Config stay exactly
  as committed.
* No PS result is stored: results come only from the backend (MongoDB -> Rule Engine -> API).
* `data_usages` and `generated_documents` are declared by the Data Schema but not read by the active PS
  Config; this script creates them empty so the database "supports" every collection the schema declares.
* There is no `template_ps` collection anywhere in the Data Schema, the Rule Engine or `ps_requirements`
  (checked against backend/app/models/source_schema.py and docs/source-of-truth/Data-Schema.md) — it is
  not created here. See the run report for this finding.

Run from backend/:
    .venv/bin/python scripts/seed_mock_data.py            # insert what is missing
    .venv/bin/python scripts/seed_mock_data.py --dry-run  # check only, write nothing
Target: MORNITOR_MOCK_DB_URI (default mongodb://localhost:27017)
        MORNITOR_MOCK_DB_NAME (default mornitor_mock; must contain "mock")
Then:   MORNITOR_DB_URI=mongodb://localhost:27017 MORNITOR_DB_NAME=mornitor_mock MORNITOR_YEAR_OFFSET=0 \\
        .venv/bin/uvicorn app.main:app --port 8000
        GET /api/monitor?curriculumCode=MOCK-IS-001
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
from app.models.source_schema import SOURCE_SCHEMA, declared_type  # noqa: E402
from app.repositories.configuration import CONFIG_TYPE_KEY  # noqa: E402
from app.services.generation_readiness import ReadinessConfigProblem, validate  # noqa: E402

PS_CONFIG_FILE = BACKEND / "tests" / "fixtures" / "ps_config_v1.json"
GENERATION_READINESS_FILE = BACKEND / "tests" / "fixtures" / "generation_readiness_v1.json"
CONFIG_COLLECTION = "ps_requirements"
MOCK_DB_NAME_RE = re.compile(r".*mock.*", re.IGNORECASE)
SOURCE_DB_DEFAULT = "mornitor_source"   # app/settings.py: the backend's real source database by default
MONITOR_OWNED = "monitoring_results"    # app/adapters/monitoring_results.py: written by the backend, not by this script
EMPTY_COLLECTIONS = ("data_usages", "generated_documents")  # declared by the Data Schema, not read by active config
STATUS = "MOCK DATA FOR THE FULL MONITOR FLOW (MOCK-IS-001)"

# -- fixed, readable ids: 5eed0000 ("seed") | collection code | record number (decimal digits) ----------
ID_PREFIX = "5eed0000"
CODES = {"curricula": "01", "persons": "02", "appointments": "03", "educations": "04",
         "academic_works": "05", CONFIG_COLLECTION: "06", "documents": "07"}
LOWEST, HIGHEST = ObjectId(ID_PREFIX + "0" * 16), ObjectId(ID_PREFIX + "f" * 16)


def tid(collection: str, number: int) -> ObjectId:
    return ObjectId(f"{ID_PREFIX}{CODES[collection]}{number:014d}")


TIMESTAMP = datetime(2026, 10, 1)  # Data Schema `timestamp`; fixed so a re-run builds identical records

CURRICULUM_CODE = "MOCK-IS-001"
CURRICULUM_ID = tid("curricula", 1)
# curriculumYear a Gregorian 2025 (project requirement): with MORNITOR_YEAR_OFFSET=0, currentYear = the
# clock's own Gregorian year (references/runtime.py), so PS-09 evaluates currentYear - curriculumYear.
CURRICULUM_YEAR = 2025

# 5 persons: every one holds BOTH programmeResponsible and programmeStaff appointments of the same
# curriculum (PS-01 needs >= 5 distinct programmeResponsible; PS-02 needs, for each of them, a
# programmeStaff appointment of the same curriculum and person). No person here is a specialInstructor:
# the mock has none, so PS-08 (naEnabled) decides N/A on its own (no subject matches targetRole).
PERSONS = {f"P00{n}": tid("persons", n) for n in range(1, 6)}

# One education per person: degree "master" or "Ph.D." (both >= the configured minimum "master" in the
# ordering bachelor < master < Ph.D.), with field and institution filled in for PS-06's reviewer evidence.
EDUCATIONS = [
    (1, "P001", "master", "Information Science", "มหาวิทยาลัยมอคข้อมูล"),
    (2, "P002", "Ph.D.", "Computer Science", "มหาวิทยาลัยมอคข้อมูล"),
    (3, "P003", "master", "Information Technology", "มหาวิทยาลัยมอคข้อมูล"),
    (4, "P004", "master", "Information Systems", "มหาวิทยาลัยมอคข้อมูล"),
    (5, "P005", "Ph.D.", "Information Science", "มหาวิทยาลัยมอคข้อมูล"),
]

# One academic work per person, publicationYear inside currentYear-5..currentYear (2021..2026 with
# MORNITOR_YEAR_OFFSET=0 and today in 2026) so PS-07's minimumCount: 1 is met for every subject.
WORKS = [
    (1, "P001", "journalArticle", "งานวิจัย Mock ของ P001", 2024, "Scopus"),
    (2, "P002", "journalArticle", "งานวิจัย Mock ของ P002", 2023, "TCI"),
    (3, "P003", "conferencePaper", "งานวิจัย Mock ของ P003", 2025, "Scopus"),
    (4, "P004", "journalArticle", "งานวิจัย Mock ของ P004", 2022, "TCI"),
    (5, "P005", "journalArticle", "งานวิจัย Mock ของ P005", 2024, "Scopus"),
]

DOCUMENTS = [
    (1, "curriculum", "MOCK-IS-001-curriculum.pdf",
     {"storage": "local", "path": "project-data/documents/original/curriculum/MOCK-IS-001-curriculum.pdf"}),
    (2, "appointment", "MOCK-IS-001-appointment.pdf",
     {"storage": "local", "path": "project-data/documents/original/appointment/MOCK-IS-001-appointment.pdf"}),
    (3, "cv", "MOCK-P001-cv.pdf", {"storage": "local", "path": "project-data/documents/original/cv/MOCK-P001-cv.pdf"}),
]


def build() -> dict[str, list[dict]]:
    """Every record to seed, in Data Schema shape (Buddhist-era date strings as its examples; curriculumYear
    is a plain Gregorian Integer per the project's explicit requirement for this mock)."""
    data: dict[str, list[dict]] = {c: [] for c in CODES}
    data["curricula"].append({
        "_id": CURRICULUM_ID, "curriculumCode": CURRICULUM_CODE,
        "curriculumName": "หลักสูตรจำลองระบบสารสนเทศ (Mock)", "curriculumYear": CURRICULUM_YEAR,
        "version": 1, "status": "latest", "timestamp": TIMESTAMP,
    })
    for key, pid in PERSONS.items():
        n = key[-1]
        data["persons"].append({
            "_id": pid, "title": "อ.", "firstName": "มอค", "lastName": key, "fullName": f"อ.มอค {key}",
            "academicPosition": "อาจารย์", "timestamp": TIMESTAMP,
        })
    appt_n = 0
    for key, pid in PERSONS.items():
        for role, role_name in (("programmeResponsible", "อาจารย์ผู้รับผิดชอบหลักสูตร"),
                                ("programmeStaff", "อาจารย์ประจำหลักสูตร")):
            appt_n += 1
            data["appointments"].append({
                "_id": tid("appointments", appt_n), "curriculumId": CURRICULUM_ID, "personId": pid,
                "role": role, "roleName": role_name, "effectiveDate": "2568-06-01",
                "appointmentOrder": {"orderNumber": f"MOCK-{appt_n}/2568", "orderDate": "2568-05-15"},
                "status": "active", "timestamp": TIMESTAMP,
            })
    for n, person, degree, field, institution in EDUCATIONS:
        data["educations"].append({
            "_id": tid("educations", n), "personId": PERSONS[person], "degree": degree, "field": field,
            "institution": institution, "graduationYear": 2553, "timestamp": TIMESTAMP,
        })
    for n, person, work_type, title, year, database in WORKS:
        data["academic_works"].append({
            "_id": tid("academic_works", n), "personId": PERSONS[person], "workType": work_type, "title": title,
            "publicationYear": year, "database": database, "timestamp": TIMESTAMP,
        })
    for n, document_type, file_name, original in DOCUMENTS:
        data["documents"].append({
            "_id": tid("documents", n), "documentType": document_type, "fileType": "pdf", "fileName": file_name,
            "curriculumId": CURRICULUM_ID, "originalFile": dict(original), "status": "processed", "timestamp": TIMESTAMP,
        })
    config = json.loads(PS_CONFIG_FILE.read_text(encoding="utf-8"))
    readiness = json.loads(GENERATION_READINESS_FILE.read_text(encoding="utf-8"))
    data[CONFIG_COLLECTION] = [{"_id": tid(CONFIG_COLLECTION, n), **copy.deepcopy(doc)}
                               for n, doc in enumerate([*config, readiness], start=1)]
    return data


def config_type_documents(data: dict[str, list[dict]]) -> list[dict]:
    return [d for d in data[CONFIG_COLLECTION] if CONFIG_TYPE_KEY in d]


def configuration_problems(data: dict[str, list[dict]]) -> list[str]:
    problems = []
    for doc in config_type_documents(data):
        try:
            validate(doc)
        except ReadinessConfigProblem as problem:
            problems.append(f"{GENERATION_READINESS_FILE.name}: {problem.issue}: {problem.detail}")
    return problems


def duplicate_problems(db, data: dict[str, list[dict]]) -> list[str]:
    problems = []
    for doc in config_type_documents(data):
        query = {CONFIG_TYPE_KEY: doc[CONFIG_TYPE_KEY], "_id": {"$ne": doc["_id"]}}
        for other in db[CONFIG_COLLECTION].find(query, {"_id": 1}):
            problems.append(f"{CONFIG_COLLECTION} {other['_id']}: another {CONFIG_TYPE_KEY} "
                            f"{doc[CONFIG_TYPE_KEY]!r} document (this script's is {doc['_id']})")
    return problems


_TYPES = {"ObjectId": ObjectId, "String": str, "Integer": int, "Boolean": bool, "Object": dict,
          "Date": datetime, "Date/String": (datetime, str)}


def schema_problems(data: dict[str, list[dict]]) -> list[str]:
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
    problems = []
    if db_name == SOURCE_DB_DEFAULT:
        problems.append(f"database '{db_name}' is the backend's real source database")
    if not MOCK_DB_NAME_RE.fullmatch(db_name):
        problems.append(f"database '{db_name}' does not look like a mock database (its name must contain 'mock')")
    return problems


def content_problems(db) -> list[str]:
    problems = []
    known = {*CODES, *EMPTY_COLLECTIONS}
    for name in sorted(db.list_collection_names()):
        if name == MONITOR_OWNED:
            continue
        if name not in known:
            problems.append(f"collection '{name}' is not part of the mock dataset")
            continue
        if name in EMPTY_COLLECTIONS:
            continue
        other = db[name].count_documents({"_id": {"$not": {"$gte": LOWEST, "$lte": HIGHEST}}})
        if other:
            problems.append(f"{name}: {other} record(s) that are not this mock's data (_id not starting with {ID_PREFIX})")
    return problems


def stop(title: str, problems: list[str]) -> None:
    print(f"STOP: {title}")
    for p in problems:
        print(f"  - {p}")
    print("Stopped: nothing (more) was written.")
    sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Insert the MOCK-IS-001 dataset (no delete, no update).")
    parser.add_argument("--dry-run", action="store_true", help="check everything, write nothing")
    args = parser.parse_args()

    uri = os.environ.get("MORNITOR_MOCK_DB_URI", "mongodb://localhost:27017")
    db_name = os.environ.get("MORNITOR_MOCK_DB_NAME", "mornitor_mock")
    print(f"Mongo URI:   {uri}")
    print(f"Database:    {db_name}")
    print(f"Environment: MOCK (a separate mock database; {SOURCE_DB_DEFAULT} and every other database are not touched)")

    if problems := target_problems(db_name):
        stop("the target is not a mock database", problems)

    collections_declared = set(SOURCE_SCHEMA) | {CONFIG_COLLECTION}
    required = {"curricula", "persons", "appointments", "educations", "academic_works", "documents",
               "data_usages", "generated_documents", CONFIG_COLLECTION, MONITOR_OWNED}
    requested = required | {"template_ps"}
    unknown = sorted(requested - collections_declared - {MONITOR_OWNED})
    if unknown:
        print("\nDATA INSUFFICIENT (ข้อมูลไม่เพียงพอ): the following requested collection(s) are not part of the "
              "Data Schema / Rule Engine and are NOT created by this script:")
        for name in unknown:
            print(f"  - {name}: no field of it is declared in backend/app/models/source_schema.py, no interpreter "
                 f"construct reads it, and it is absent from docs/source-of-truth/Data-Schema.md")
        print("  Reported instead of guessed, per the project's own instruction not to invent collections.\n")

    data = build()
    if problems := schema_problems(data):
        stop("the dataset does not match the Data Schema", problems)
    if problems := configuration_problems(data):
        stop("the generation readiness configuration is not valid", problems)

    client = MongoClient(uri, serverSelectionTimeoutMS=3000)
    client.admin.command("ping")
    db = client[db_name]
    existed = db_name in client.list_database_names()
    print(f"Database exists: {'yes' if existed else 'no (created by the first insert)'}")
    print(f"Collections: {', '.join(sorted(db.list_collection_names())) or '(none)'}")
    if problems := content_problems(db):
        stop("the database holds data that is not this mock dataset", problems)
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
            if problems := target_problems(db.name):
                stop("the target is not a mock database", problems)
            try:
                db[collection].insert_one(doc)
                inserted[collection] += 1
            except DuplicateKeyError:
                present[collection] += 1

    empty_created = []
    if not args.dry_run:
        for name in EMPTY_COLLECTIONS:
            if name not in db.list_collection_names():
                db.create_collection(name)
                empty_created.append(name)

    total_new = sum(inserted.values())
    print()
    if args.dry_run:
        print(f"DRY RUN: {total_new} record(s) would be inserted; nothing was written")
    elif total_new == 0 and not empty_created:
        print("Mock Data already exists")
    else:
        print("MOCK DATA INSERTED")
    print(f"\nDatabase:\n{db_name}")
    print(f"\nCurriculum:\n{CURRICULUM_CODE}  curriculumYear={CURRICULUM_YEAR}  _id={CURRICULUM_ID}")
    print("\nPersons (mock id -> persons._id):")
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
    if empty_created:
        print(f"\nEmpty collections created (declared by the Data Schema, not read by the active PS Config): "
             f"{', '.join(empty_created)}")
    print(f"\n'template_ps' collection: NOT created — ข้อมูลไม่เพียงพอ (see DATA INSUFFICIENT note above)")
    if differs:
        print("\nAlready present but different from this script (left unchanged, never overwritten):")
        for d in differs:
            print(f"  - {d}")
    print(f"\nStatus:\n{STATUS}")


if __name__ == "__main__":
    main()
