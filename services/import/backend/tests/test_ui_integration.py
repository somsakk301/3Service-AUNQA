import os
from datetime import datetime, timezone
from typing import Any

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


def test_import_page_assets_and_curriculum_options() -> None:
    settings = get_settings()
    mongo_client: MongoClient[dict[str, Any]] = MongoClient(settings.mongodb_uri)
    database = mongo_client.get_default_database()
    curriculum_id = ObjectId()
    database["curricula"].insert_one(
        {
            "_id": curriculum_id,
            "curriculumCode": "PHASE10-UI",
            "curriculumName": "Import Page Integration",
            "curriculumYear": 2026,
            "version": 1,
            "status": "active",
            "sources": [],
            "timestamp": datetime.now(timezone.utc),
        }
    )
    try:
        with TestClient(app) as client:
            page = client.get("/")
            stylesheet = client.get("/static/app.css")
            script = client.get("/static/app.js")
            curricula = client.get("/api/curricula")
            persons = client.get("/api/persons")

        assert page.status_code == 200
        assert "Import Document" in page.text
        assert 'value="curriculum"' in page.text
        assert 'value="cv"' in page.text
        assert 'value="appointment"' in page.text
        assert 'value="template"' in page.text
        assert 'id="template-version"' in page.text
        assert 'id="curriculum-version"' in page.text
        assert 'id="curriculum-status"' in page.text
        assert "PDF, DOC และ DOCX" in page.text
        assert 'type="file" accept=".pdf,.doc,.docx" multiple' in page.text
        assert stylesheet.status_code == 200
        assert "--green:" in stylesheet.text
        assert script.status_code == 200
        assert 'fetch("/api/import/preview"' in script.text
        assert 'fetch("/api/import/confirm"' in script.text
        assert 'fetch("/api/templates"' in script.text
        assert 'fetch("/api/persons"' in script.text
        assert 'templateMode ? ".docx,.pdf"' in script.text
        assert "const curriculumMode = documentType === \"curriculum\"" in script.text
        assert 'payload.append("curriculumVersion"' in script.text
        assert "Confirm Import" in page.text
        assert 'id="preview-panel"' in page.text
        assert "for (let index = 0; index < selectedFiles.length" in script.text
        assert "Import Queue Completed" in script.text
        assert "const collectionFormSchemas" in script.text
        assert 'label: "รหัสหลักสูตร"' in script.text
        assert 'label: "บุคลากรเจ้าของวุฒิ"' in script.text
        assert 'label: "มีประสบการณ์สอน"' in script.text
        assert "sourceSummary(item, record)" in script.text
        assert "validatePreviewForms()" in script.text
        assert "JSON.stringify(record, null, 2)" not in script.text
        assert ".preview-form-grid" in stylesheet.text
        assert ".preview-source" in stylesheet.text

        assert curricula.status_code == 200
        assert persons.status_code == 200
        matching = [
            item
            for item in curricula.json()
            if item["curriculumId"] == str(curriculum_id)
        ]
        assert matching == [
            {
                "curriculumId": str(curriculum_id),
                "curriculumCode": "PHASE10-UI",
                "curriculumName": "Import Page Integration",
                "curriculumYear": 2026,
                "version": 1,
            }
        ]
    finally:
        database["curricula"].delete_one({"_id": curriculum_id})
        mongo_client.close()
