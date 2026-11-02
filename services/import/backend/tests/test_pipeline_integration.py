import os
from datetime import datetime, timezone
from io import BytesIO
from pathlib import PurePosixPath
from typing import Any

import pytest
from bson import ObjectId
from docx import Document as WordDocument
from pymongo import MongoClient

from app.config import Settings
from app.database.bootstrap import ensure_database_schema
from app.pipeline import ImportPipeline
from app.services.document_import import DocumentImportService
from app.services.file_validation import ValidatedUpload
from app.vectorization import BgeM3Embedder, ChromaVectorStore

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_INTEGRATION_TESTS") != "1",
        reason="set RUN_INTEGRATION_TESTS=1 to use Docker Compose services",
    ),
]


class PipelineEmbeddingModel:
    """Deterministic 1024-d test double; production still uses BAAI/bge-m3."""

    def encode(self, sentences: list[str], **kwargs: object) -> dict[str, object]:
        return {
            "dense_vecs": [
                [float(index == 0) for index in range(1024)] for _ in sentences
            ]
        }


def _docx_bytes(lines: list[str]) -> bytes:
    document = WordDocument()
    for line in lines:
        document.add_paragraph(line)
    stream = BytesIO()
    document.save(stream)
    return stream.getvalue()


def _upload(
    service: DocumentImportService,
    *,
    document_type: str,
    curriculum_id: ObjectId,
    lines: list[str],
) -> ObjectId:
    result = service.import_document(
        upload=ValidatedUpload(
            document_type=document_type,
            file_name=f"pipeline-{document_type}.docx",
            extension=".docx",
            content=_docx_bytes(lines),
        ),
        curriculum_id=str(curriculum_id),
    )
    return ObjectId(result["documentId"])


def _stored_paths(
    settings: Settings,
    document: dict[str, Any] | None,
) -> list[Any]:
    if document is None:
        return []
    paths = []
    for field in ("originalFile", "convertedFile", "extractedText"):
        raw_path = document[field]["path"]
        if not raw_path:
            continue
        relative = PurePosixPath(raw_path).relative_to("project-data")
        paths.append(settings.project_data_root.joinpath(*relative.parts))
    return paths


def test_pipeline_processes_all_document_types_and_relationships() -> None:
    settings = Settings()
    client: MongoClient[dict[str, Any]] = MongoClient(settings.mongodb_uri)
    database = client.get_default_database()
    ensure_database_schema(database)
    store = ChromaVectorStore(settings)
    pipeline = ImportPipeline(
        settings,
        database,
        embedder=BgeM3Embedder(settings, model=PipelineEmbeddingModel()),
        vector_store=store,
    )
    imports = DocumentImportService(settings, database)

    suffix = str(ObjectId())
    curriculum_code = f"PIPELINE-{suffix}"
    person_name = f"Dr. Pipeline {suffix}"
    curriculum_id = ObjectId()
    document_ids: list[ObjectId] = []
    stored_paths: list[Any] = []
    record_ids: dict[str, set[ObjectId]] = {
        "persons": set(),
        "educations": set(),
        "academic_works": set(),
        "appointments": set(),
        "data_usages": set(),
    }
    database["curricula"].insert_one(
        {
            "_id": curriculum_id,
            "curriculumCode": curriculum_code,
            "curriculumName": "Pipeline Integration",
            "curriculumYear": 2026,
            "version": 1,
            "status": "active",
            "sources": [],
            "timestamp": datetime.now(timezone.utc),
        }
    )

    try:
        curriculum_document_id = _upload(
            imports,
            document_type="curriculum",
            curriculum_id=curriculum_id,
            lines=[
                f"curriculumCode: {curriculum_code}",
                "curriculumName: Pipeline Integration",
                "curriculumYear: 2026",
                "version: 1",
                "status: active",
                "1.1 อาจารย์ผู้รับผิดชอบหลักสูตร จำนวน 1 คน",
                "1",
                person_name,
                "Ph.D.",
                "Computer Science",
                "2020",
                "Seed University",
            ],
        )
        document_ids.append(curriculum_document_id)
        curriculum_result = pipeline.process(curriculum_document_id)
        assert curriculum_result.status == "processed"
        assert curriculum_result.structuredRecords["curriculum"] == (
            str(curriculum_id),
        )
        seeded_person_id = ObjectId(
            curriculum_result.structuredRecords["person"][0]
        )
        record_ids["persons"].add(seeded_person_id)
        record_ids["educations"].update(
            ObjectId(value)
            for value in curriculum_result.structuredRecords["education"]
        )

        cv_document_id = _upload(
            imports,
            document_type="cv",
            curriculum_id=curriculum_id,
            lines=[
                f"Full Name: {person_name}",
                "Education:",
                "Ph.D. | Computing | Test University | 2020",
                "Academic Works:",
                "Journal | Pipeline Integration | 2026 | Scopus | Q1",
                "Teaching Experience:",
                "courseName | institution | period",
                "Database Systems | Test University | 2021-2025",
            ],
        )
        document_ids.append(cv_document_id)
        cv_result = pipeline.process(cv_document_id)
        person_id = ObjectId(cv_result.structuredRecords["person"][0])
        assert person_id == seeded_person_id
        record_ids["persons"].add(person_id)
        record_ids["educations"].update(
            ObjectId(value) for value in cv_result.structuredRecords["education"]
        )
        record_ids["academic_works"].update(
            ObjectId(value) for value in cv_result.structuredRecords["academicWork"]
        )
        assert database["persons"].find_one(
            {"_id": person_id}
        )["hasTeachingExperience"] is True
        person_record = database["persons"].find_one({"_id": person_id})
        assert person_record is not None
        assert {source["documentId"] for source in person_record["sources"]} == {
            curriculum_document_id,
            cv_document_id,
        }

        second_cv_document_id = _upload(
            imports,
            document_type="cv",
            curriculum_id=curriculum_id,
            lines=[
                f"Full Name: {person_name}",
                "Education:",
                "Ph.D. | Computing | Test University | 2020",
                "Academic Works:",
                "Journal | Pipeline Integration | 2026 | Scopus | Q1",
                "Teaching Experience:",
                "Database Systems | Test University | 2021-2025",
            ],
        )
        document_ids.append(second_cv_document_id)
        second_cv_result = pipeline.process(second_cv_document_id)
        assert second_cv_result.structuredRecords["academicWork"] == (
            cv_result.structuredRecords["academicWork"][0],
        )
        merged_work = database["academic_works"].find_one(
            {"_id": ObjectId(cv_result.structuredRecords["academicWork"][0])}
        )
        assert merged_work is not None
        assert {source["documentId"] for source in merged_work["sources"]} == {
            cv_document_id,
            second_cv_document_id,
        }

        appointment_document_id = _upload(
            imports,
            document_type="appointment",
            curriculum_id=curriculum_id,
            lines=[
                f"Full Name: {person_name}",
                f"Curriculum Code: {curriculum_code}",
                "role: programmeResponsible",
                "roleName: Programme Chair",
                "effectiveDate: 2026-01-01",
                "orderNumber: PIPELINE/2026",
                "orderDate: 2025-12-01",
                "status: active",
            ],
        )
        document_ids.append(appointment_document_id)
        appointment_result = pipeline.process(appointment_document_id)
        appointment_id = ObjectId(
            appointment_result.structuredRecords["appointment"][0]
        )
        record_ids["appointments"].add(appointment_id)

        appointment = database["appointments"].find_one({"_id": appointment_id})
        assert appointment is not None
        assert appointment["personId"] == person_id
        assert appointment["curriculumId"] == curriculum_id
        assert all(
            database["documents"].find_one({"_id": document_id})["status"]
            == "processed"
            for document_id in document_ids
        )

        for result, document_id in (
            (curriculum_result, curriculum_document_id),
            (cv_result, cv_document_id),
            (appointment_result, appointment_document_id),
        ):
            vector_ids = store.get_document_ids(str(document_id))
            assert len(vector_ids) == result.chunkCount
            assert vector_ids

        usage_records = list(
            database["data_usages"].find({"curriculumId": curriculum_id})
        )
        record_ids["data_usages"].update(item["_id"] for item in usage_records)
        assert {item["dataType"] for item in usage_records} == {
            "curriculum",
            "person",
            "education",
            "academicWork",
            "appointment",
        }
        assert database["generated_documents"].count_documents(
            {"curriculumId": curriculum_id}
        ) == 0
    finally:
        for document_id in document_ids:
            document = database["documents"].find_one({"_id": document_id})
            stored_paths.extend(_stored_paths(settings, document))
            store.delete_document(str(document_id))
        database["documents"].delete_many({"_id": {"$in": document_ids}})
        for collection_name in (
            "data_usages",
            "appointments",
            "academic_works",
            "educations",
            "persons",
        ):
            ids = list(record_ids[collection_name])
            if ids:
                database[collection_name].delete_many({"_id": {"$in": ids}})
        database["curricula"].delete_one({"_id": curriculum_id})
        for path in stored_paths:
            path.unlink(missing_ok=True)
        client.close()


def test_pipeline_marks_parse_failure_and_leaves_no_vectors() -> None:
    settings = Settings()
    client: MongoClient[dict[str, Any]] = MongoClient(settings.mongodb_uri)
    database = client.get_default_database()
    ensure_database_schema(database)
    store = ChromaVectorStore(settings)
    pipeline = ImportPipeline(
        settings,
        database,
        embedder=BgeM3Embedder(settings, model=PipelineEmbeddingModel()),
        vector_store=store,
    )
    imports = DocumentImportService(settings, database)
    curriculum_id = ObjectId()
    document_id: ObjectId | None = None
    stored_paths: list[Any] = []
    database["curricula"].insert_one(
        {
            "_id": curriculum_id,
            "curriculumCode": f"PIPELINE-FAIL-{curriculum_id}",
            "curriculumName": "Pipeline Failure",
            "curriculumYear": 2026,
            "version": 1,
            "status": "active",
            "sources": [],
            "timestamp": datetime.now(timezone.utc),
        }
    )
    try:
        document_id = _upload(
            imports,
            document_type="cv",
            curriculum_id=curriculum_id,
            lines=["Full Name: Dr. Incomplete CV"],
        )
        with pytest.raises(Exception, match="Education"):
            pipeline.process(document_id)
        record = database["documents"].find_one({"_id": document_id})
        assert record is not None
        assert record["status"] == "failed"
        assert store.get_document_ids(str(document_id)) == set()
    finally:
        if document_id is not None:
            document = database["documents"].find_one({"_id": document_id})
            stored_paths.extend(_stored_paths(settings, document))
            store.delete_document(str(document_id))
            database["documents"].delete_one({"_id": document_id})
        database["curricula"].delete_one({"_id": curriculum_id})
        for path in stored_paths:
            path.unlink(missing_ok=True)
        client.close()
