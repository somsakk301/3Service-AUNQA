import json
import os
from datetime import datetime, timezone
from io import BytesIO
from pathlib import PurePosixPath
from typing import Any

import chromadb
import pytest
from bson import ObjectId
from docx import Document as WordDocument
from fastapi.testclient import TestClient
from pymongo import MongoClient

from app.config import get_settings
from app.main import app
from app.pipeline import ImportPipeline
from app.vectorization import BgeM3Embedder, ChromaVectorStore


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_INTEGRATION_TESTS") != "1",
        reason="set RUN_INTEGRATION_TESTS=1 to use Docker Compose services",
    ),
]


def _cv_bytes() -> bytes:
    document = WordDocument()
    for line in (
        "Full Name: Dr. Preview Only",
        "Education:",
        "Ph.D. | Computer Science | Preview University | 2024",
        "Academic Works:",
        "Journal | Preview Must Not Write | 2026 | Scopus | Q1",
        "Teaching Experience:",
        "Database Systems | Preview University | 2024-2026",
    ):
        document.add_paragraph(line)
    stream = BytesIO()
    document.save(stream)
    return stream.getvalue()


def _curriculum_bytes() -> bytes:
    document = WordDocument()
    for line in (
        "Curriculum Code: BOOTSTRAP-IIT-2570",
        "Curriculum Name: Bachelor of Science in Intelligent Information Technology",
        "Curriculum Year: 2570",
    ):
        document.add_paragraph(line)
    stream = BytesIO()
    document.save(stream)
    return stream.getvalue()


class PreviewEmbeddingModel:
    def encode(self, sentences: list[str], **kwargs: object) -> dict[str, object]:
        return {
            "dense_vecs": [
                [float(index == 0) for index in range(1024)] for _ in sentences
            ]
        }


def test_curriculum_bootstrap_preview_and_confirm_without_existing_curriculum() -> None:
    settings = get_settings()
    mongo_client: MongoClient[dict[str, Any]] = MongoClient(settings.mongodb_uri)
    database = mongo_client.get_default_database()
    store = ChromaVectorStore(settings)
    content = _curriculum_bytes()
    document_id: ObjectId | None = None
    curriculum_id: ObjectId | None = None
    try:
        assert database["curricula"].count_documents(
            {"curriculumCode": "BOOTSTRAP-IIT-2570"}
        ) == 0
        with TestClient(app) as client:
            app.state.import_pipeline = ImportPipeline(
                settings,
                database,
                embedder=BgeM3Embedder(settings, model=PreviewEmbeddingModel()),
                vector_store=store,
            )
            preview_response = client.post(
                "/api/import/preview",
                data={
                    "documentType": "curriculum",
                    "curriculumVersion": "1",
                    "curriculumStatus": "active",
                },
                files={
                    "file": (
                        "bootstrap-curriculum.docx",
                        content,
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    )
                },
            )
            assert preview_response.status_code == 200, preview_response.text
            preview = preview_response.json()
            curriculum_id = ObjectId(preview["curriculumId"])
            assert database["curricula"].find_one({"_id": curriculum_id}) is None
            curriculum = preview["collections"]["curricula"][0]
            assert curriculum["version"] == 1
            assert curriculum["status"] == "active"
            assert curriculum["sources"][0]["fieldPaths"] == [
                "curriculumCode",
                "curriculumName",
                "curriculumYear",
            ]

            confirm_response = client.post(
                "/api/import/confirm",
                data={
                    "documentType": "curriculum",
                    "curriculumId": str(curriculum_id),
                    "previewData": json.dumps(preview),
                },
                files={
                    "file": (
                        "bootstrap-curriculum.docx",
                        content,
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    )
                },
            )

        assert confirm_response.status_code == 201, confirm_response.text
        result = confirm_response.json()
        document_id = ObjectId(result["documentId"])
        assert result["structuredRecords"]["curriculum"] == [str(curriculum_id)]
        assert database["documents"].find_one({"_id": document_id})[
            "curriculumId"
        ] == curriculum_id
        stored = database["curricula"].find_one({"_id": curriculum_id})
        assert stored is not None
        assert stored["sources"][0]["documentId"] == document_id
    finally:
        if document_id is not None:
            document = database["documents"].find_one({"_id": document_id})
            if document is not None:
                relative = PurePosixPath(document["originalFile"]["path"]).relative_to(
                    "project-data"
                )
                settings.project_data_root.joinpath(*relative.parts).unlink(
                    missing_ok=True
                )
            store.delete_document(str(document_id))
            database["documents"].delete_one({"_id": document_id})
        if curriculum_id is not None:
            database["data_usages"].delete_many({"curriculumId": curriculum_id})
            database["curricula"].delete_one({"_id": curriculum_id})
        mongo_client.close()


def test_preview_returns_editable_data_without_database_writes() -> None:
    settings = get_settings()
    mongo_client: MongoClient[dict[str, Any]] = MongoClient(settings.mongodb_uri)
    database = mongo_client.get_default_database()
    curriculum_id = ObjectId()
    database["curricula"].insert_one(
        {
            "_id": curriculum_id,
            "curriculumCode": "PREVIEW-NOWRITE",
            "curriculumName": "Preview No Write",
            "curriculumYear": 2026,
            "version": 1,
            "status": "active",
            "sources": [],
            "timestamp": datetime.now(timezone.utc),
        }
    )
    tracked = (
        "persons",
        "educations",
        "academic_works",
        "appointments",
        "documents",
        "data_usages",
    )
    before = {name: database[name].count_documents({}) for name in tracked}
    chroma_client = chromadb.HttpClient(
        host=settings.chromadb_host,
        port=settings.chromadb_port,
    )
    vector_collection = chroma_client.get_or_create_collection("document_chunks")
    vectors_before = vector_collection.count()

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/import/preview",
                data={
                    "documentType": "cv",
                    "curriculumId": str(curriculum_id),
                },
                files={
                    "file": (
                        "preview-cv.docx",
                        _cv_bytes(),
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    )
                },
            )
            forged = response.json()
            forged["collections"]["persons"][0]["sources"][0][
                "documentId"
            ] = str(ObjectId())
            forged_response = client.post(
                "/api/import/confirm",
                data={
                    "documentType": "cv",
                    "curriculumId": str(curriculum_id),
                    "previewData": json.dumps(forged),
                },
                files={
                    "file": (
                        "preview-cv.docx",
                        _cv_bytes(),
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    )
                },
            )

        assert response.status_code == 200, response.text
        preview = response.json()
        assert preview["documentType"] == "cv"
        assert preview["collections"]["persons"][0]["firstName"] == "Preview"
        assert preview["collections"]["educations"]
        assert preview["collections"]["academic_works"]
        assert preview["chunks"]
        assert preview["collections"]["persons"][0]["sources"] == [
            {
                "documentId": preview["previewId"],
                "pageNumbers": [],
                "fieldPaths": [
                    "academicPosition",
                    "firstName",
                    "fullName",
                    "hasTeachingExperience",
                    "lastName",
                    "title",
                ],
            }
        ]
        assert forged_response.status_code == 422
        assert "must match the confirmed document" in forged_response.text
        assert all(len(chunk["text"]) <= 500 for chunk in preview["chunks"])
        assert {name: database[name].count_documents({}) for name in tracked} == before
        assert vector_collection.count() == vectors_before
        preview_path = (
            settings.project_data_root
            / "documents"
            / "original"
            / "cv"
            / f"{preview['previewId']}.docx"
        )
        assert not preview_path.exists()
    finally:
        database["curricula"].delete_one({"_id": curriculum_id})
        mongo_client.close()


def test_confirm_persists_the_edited_preview() -> None:
    settings = get_settings()
    mongo_client: MongoClient[dict[str, Any]] = MongoClient(settings.mongodb_uri)
    database = mongo_client.get_default_database()
    curriculum_id = ObjectId()
    database["curricula"].insert_one(
        {
            "_id": curriculum_id,
            "curriculumCode": "PREVIEW-CONFIRM",
            "curriculumName": "Preview Confirm",
            "curriculumYear": 2026,
            "version": 1,
            "status": "active",
            "sources": [],
            "timestamp": datetime.now(timezone.utc),
        }
    )
    store = ChromaVectorStore(settings)
    document_id: ObjectId | None = None
    structured_ids: dict[str, list[str]] = {}
    stored_paths = []
    content = _cv_bytes()
    try:
        with TestClient(app) as client:
            app.state.import_pipeline = ImportPipeline(
                settings,
                database,
                embedder=BgeM3Embedder(settings, model=PreviewEmbeddingModel()),
                vector_store=store,
            )
            preview_response = client.post(
                "/api/import/preview",
                data={"documentType": "cv", "curriculumId": str(curriculum_id)},
                files={
                    "file": (
                        "confirm-cv.docx",
                        content,
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    )
                },
            )
            assert preview_response.status_code == 200, preview_response.text
            preview = preview_response.json()
            preview["collections"]["academic_works"][0]["title"] = (
                "Edited and confirmed title"
            )
            preview["collections"]["educations"] = []
            confirm_response = client.post(
                "/api/import/confirm",
                data={
                    "documentType": "cv",
                    "curriculumId": str(curriculum_id),
                    "previewData": json.dumps(preview),
                },
                files={
                    "file": (
                        "confirm-cv.docx",
                        content,
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    )
                },
            )

        assert confirm_response.status_code == 201, confirm_response.text
        result = confirm_response.json()
        document_id = ObjectId(result["documentId"])
        structured_ids = result["structuredRecords"]
        assert result["status"] == "processed"
        assert result["chunkCount"] == len(store.get_document_ids(str(document_id)))
        assert structured_ids["education"] == []
        work_id = ObjectId(structured_ids["academicWork"][0])
        person_id = ObjectId(structured_ids["person"][0])
        assert database["academic_works"].find_one({"_id": work_id})["title"] == (
            "Edited and confirmed title"
        )
        for record in (
            database["persons"].find_one({"_id": person_id}),
            database["academic_works"].find_one({"_id": work_id}),
        ):
            assert record is not None
            assert record["sources"]
            assert record["sources"][0]["documentId"] == document_id
    finally:
        if document_id is not None:
            document = database["documents"].find_one({"_id": document_id})
            if document:
                for field in ("originalFile", "convertedFile", "extractedText"):
                    value = document[field]["path"]
                    if value:
                        relative = PurePosixPath(value).relative_to("project-data")
                        stored_paths.append(
                            settings.project_data_root.joinpath(*relative.parts)
                        )
            store.delete_document(str(document_id))
            database["documents"].delete_one({"_id": document_id})
        for collection_name, result_key in (
            ("data_usages", "dataUsage"),
            ("academic_works", "academicWork"),
            ("educations", "education"),
            ("persons", "person"),
        ):
            ids = [ObjectId(value) for value in structured_ids.get(result_key, [])]
            if ids:
                database[collection_name].delete_many({"_id": {"$in": ids}})
        database["curricula"].delete_one({"_id": curriculum_id})
        for path in stored_paths:
            path.unlink(missing_ok=True)
        mongo_client.close()
