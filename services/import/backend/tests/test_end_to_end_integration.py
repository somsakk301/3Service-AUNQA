import os
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path, PurePosixPath
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


class EndToEndEmbeddingModel:
    """Fast deterministic model used only to exercise the complete HTTP flow."""

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


def _artifact_paths(settings: Any, record: dict[str, Any] | None) -> list[Path]:
    if record is None:
        return []
    paths: list[Path] = []
    for field in ("originalFile", "convertedFile", "extractedText"):
        stored_path = record[field]["path"]
        if stored_path:
            relative = PurePosixPath(stored_path).relative_to("project-data")
            paths.append(settings.project_data_root.joinpath(*relative.parts))
    return paths


def test_http_upload_to_processed_is_traceable_end_to_end() -> None:
    settings = get_settings()
    mongo_client: MongoClient[dict[str, Any]] = MongoClient(settings.mongodb_uri)
    database = mongo_client.get_default_database()
    chroma_client = chromadb.HttpClient(
        host=settings.chromadb_host,
        port=settings.chromadb_port,
    )
    vector_store = ChromaVectorStore(settings, client=chroma_client)
    curriculum_id = ObjectId()
    suffix = str(ObjectId())
    person_name = f"Dr. HTTP Pipeline {suffix}"
    document_id: ObjectId | None = None
    artifact_paths: list[Path] = []
    created_ids: dict[str, list[ObjectId]] = {
        "persons": [],
        "educations": [],
        "academic_works": [],
        "data_usages": [],
    }
    database["curricula"].insert_one(
        {
            "_id": curriculum_id,
            "curriculumCode": f"HTTP-E2E-{suffix}",
            "curriculumName": "HTTP End-to-End",
            "curriculumYear": 2026,
            "version": 1,
            "status": "active",
            "sources": [],
            "timestamp": datetime.now(timezone.utc),
        }
    )

    try:
        with TestClient(app) as client:
            app.state.import_pipeline = ImportPipeline(
                settings,
                database,
                embedder=BgeM3Embedder(
                    settings,
                    model=EndToEndEmbeddingModel(),
                ),
                vector_store=vector_store,
            )
            upload_response = client.post(
                "/api/import",
                data={
                    "documentType": "cv",
                    "curriculumId": str(curriculum_id),
                },
                files={
                    "file": (
                        "http-cv.docx",
                        _docx_bytes(
                            [
                                f"Full Name: {person_name}",
                                "Education:",
                                "Ph.D. | Computing | HTTP University | 2020",
                                "M.Sc. | Information Systems | HTTP University | 2015",
                                "Academic Works:",
                                "Journal | HTTP Traceability | 2026 | Scopus | Q1",
                            ]
                        ),
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    )
                },
            )
            assert upload_response.status_code == 201, upload_response.text
            document_id = ObjectId(upload_response.json()["documentId"])
            uploaded_record = database["documents"].find_one({"_id": document_id})
            assert uploaded_record is not None
            assert uploaded_record["status"] == "uploaded"

            process_response = client.post(f"/api/import/{document_id}/process")
            assert process_response.status_code == 200, process_response.text
            result = process_response.json()
            assert result["status"] == "processed"

            repeated_response = client.post(f"/api/import/{document_id}/process")
            assert repeated_response.status_code == 409

        record = database["documents"].find_one({"_id": document_id})
        assert record is not None
        artifact_paths.extend(_artifact_paths(settings, record))
        assert record["status"] == "processed"
        assert record["curriculumId"] == curriculum_id
        assert not Path(record["originalFile"]["path"]).is_absolute()
        assert all(path.is_file() for path in artifact_paths)

        person_id = ObjectId(result["structuredRecords"]["person"][0])
        education_ids = [
            ObjectId(value) for value in result["structuredRecords"]["education"]
        ]
        work_ids = [
            ObjectId(value) for value in result["structuredRecords"]["academicWork"]
        ]
        usage_ids = [
            ObjectId(value) for value in result["structuredRecords"]["dataUsage"]
        ]
        created_ids["persons"].append(person_id)
        created_ids["educations"].extend(education_ids)
        created_ids["academic_works"].extend(work_ids)
        created_ids["data_usages"].extend(usage_ids)

        assert database["persons"].count_documents(
            {"_id": person_id, "fullName": person_name}
        ) == 1
        assert database["persons"].find_one(
            {"_id": person_id}
        )["hasTeachingExperience"] is False
        assert database["educations"].count_documents(
            {"_id": {"$in": education_ids}, "personId": person_id}
        ) == 2
        assert database["academic_works"].count_documents(
            {"_id": {"$in": work_ids}, "personId": person_id}
        ) == 1
        assert database["data_usages"].count_documents(
            {
                "_id": {"$in": usage_ids},
                "curriculumId": curriculum_id,
                "dataId": {"$type": "objectId"},
            }
        ) == 4
        assert database["generated_documents"].count_documents(
            {"curriculumId": curriculum_id}
        ) == 0

        vectors = chroma_client.get_collection("document_chunks").get(
            where={"documentId": str(document_id)},
            include=["documents", "embeddings", "metadatas"],
        )
        assert len(vectors["ids"]) == result["chunkCount"]
        assert vectors["ids"]
        assert all(len(vector) == 1024 for vector in vectors["embeddings"])
        assert all(text for text in vectors["documents"])
        assert all(
            metadata["documentId"] == str(document_id)
            and metadata["curriculumId"] == str(curriculum_id)
            and metadata["documentType"] == "cv"
            and metadata["personId"] == str(person_id)
            and metadata["page"] >= 1
            and metadata["chunkIndex"] >= 1
            for metadata in vectors["metadatas"]
        )
        assert all(
            chunk_id.startswith(f"{document_id}-p") and "-c" in chunk_id
            for chunk_id in vectors["ids"]
        )
    finally:
        if document_id is not None:
            record = database["documents"].find_one({"_id": document_id})
            artifact_paths.extend(_artifact_paths(settings, record))
            vector_store.delete_document(str(document_id))
            database["documents"].delete_one({"_id": document_id})
        for collection_name in (
            "data_usages",
            "academic_works",
            "educations",
            "persons",
        ):
            ids = created_ids[collection_name]
            if ids:
                database[collection_name].delete_many({"_id": {"$in": ids}})
        database["curricula"].delete_one({"_id": curriculum_id})
        for path in set(artifact_paths):
            path.unlink(missing_ok=True)
        mongo_client.close()


def test_http_pipeline_failure_sets_failed_without_vectors() -> None:
    settings = get_settings()
    mongo_client: MongoClient[dict[str, Any]] = MongoClient(settings.mongodb_uri)
    database = mongo_client.get_default_database()
    vector_store = ChromaVectorStore(settings)
    curriculum_id = ObjectId()
    document_id: ObjectId | None = None
    artifact_paths: list[Path] = []
    database["curricula"].insert_one(
        {
            "_id": curriculum_id,
            "curriculumCode": f"HTTP-FAIL-{curriculum_id}",
            "curriculumName": "HTTP Failure",
            "curriculumYear": 2026,
            "version": 1,
            "status": "active",
            "sources": [],
            "timestamp": datetime.now(timezone.utc),
        }
    )
    try:
        with TestClient(app) as client:
            app.state.import_pipeline = ImportPipeline(
                settings,
                database,
                embedder=BgeM3Embedder(
                    settings,
                    model=EndToEndEmbeddingModel(),
                ),
                vector_store=vector_store,
            )
            upload_response = client.post(
                "/api/import",
                data={
                    "documentType": "cv",
                    "curriculumId": str(curriculum_id),
                },
                files={
                    "file": (
                        "invalid-cv.docx",
                        _docx_bytes(["Full Name: Dr. Missing Sections"]),
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    )
                },
            )
            assert upload_response.status_code == 201
            document_id = ObjectId(upload_response.json()["documentId"])
            process_response = client.post(f"/api/import/{document_id}/process")
            assert process_response.status_code == 500
            assert process_response.json()["detail"] == "Import processing failed"

        record = database["documents"].find_one({"_id": document_id})
        assert record is not None
        artifact_paths.extend(_artifact_paths(settings, record))
        assert record["status"] == "failed"
        assert vector_store.get_document_ids(str(document_id)) == set()
    finally:
        if document_id is not None:
            record = database["documents"].find_one({"_id": document_id})
            artifact_paths.extend(_artifact_paths(settings, record))
            vector_store.delete_document(str(document_id))
            database["documents"].delete_one({"_id": document_id})
        database["curricula"].delete_one({"_id": curriculum_id})
        for path in set(artifact_paths):
            path.unlink(missing_ok=True)
        mongo_client.close()
