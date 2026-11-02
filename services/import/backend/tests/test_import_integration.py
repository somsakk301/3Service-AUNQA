import os
from datetime import datetime, timezone
from pathlib import PurePosixPath

import fitz
import pytest
from bson import ObjectId
from fastapi.testclient import TestClient
from pymongo import MongoClient

from app.config import get_settings
from app.main import app

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_INTEGRATION_TESTS") != "1",
        reason="set RUN_INTEGRATION_TESTS=1 to use Docker Compose services",
    ),
]


def make_pdf() -> bytes:
    document = fitz.open()
    document.new_page()
    content = document.tobytes()
    document.close()
    return content


def test_upload_persists_original_and_exact_document_schema() -> None:
    settings = get_settings()
    mongo_client = MongoClient(settings.mongodb_uri)
    database = mongo_client.get_default_database()
    curriculum_id = ObjectId()
    document_id: ObjectId | None = None
    stored_path = None

    database["curricula"].insert_one(
        {
            "_id": curriculum_id,
            "curriculumCode": "INTEGRATION-TEST",
            "curriculumName": "Integration Test Curriculum",
            "curriculumYear": 2026,
            "version": 1,
            "status": "test",
            "sources": [],
            "timestamp": datetime.now(timezone.utc),
        }
    )

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/import",
                data={
                    "documentType": "cv",
                    "curriculumId": str(curriculum_id),
                },
                files={"file": ("teacher.pdf", make_pdf(), "application/pdf")},
            )

        assert response.status_code == 201, response.text
        payload = response.json()
        document_id = ObjectId(payload["documentId"])
        record = database["documents"].find_one({"_id": document_id})
        assert record is not None
        assert set(record) == {
            "_id",
            "documentType",
            "fileType",
            "fileName",
            "curriculumId",
            "originalFile",
            "convertedFile",
            "extractedText",
            "status",
            "timestamp",
        }
        assert record["curriculumId"] == curriculum_id
        assert record["status"] == "uploaded"
        assert record["originalFile"]["storage"] == "local"
        assert record["originalFile"]["path"].startswith(
            "project-data/documents/original/cv/"
        )

        relative_path = PurePosixPath(record["originalFile"]["path"]).relative_to(
            "project-data"
        )
        stored_path = settings.project_data_root.joinpath(*relative_path.parts)
        assert stored_path.read_bytes().startswith(b"%PDF")
    finally:
        if document_id is not None:
            database["documents"].delete_one({"_id": document_id})
        database["curricula"].delete_one({"_id": curriculum_id})
        if stored_path is not None:
            stored_path.unlink(missing_ok=True)
        mongo_client.close()

