import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory

import fitz
import pytest
from bson import ObjectId
from docx import Document as WordDocument
from pymongo import MongoClient

from app.config import get_settings
from app.database.bootstrap import ensure_database_schema
from app.extraction.service import DocumentExtractionService

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_INTEGRATION_TESTS") != "1",
        reason="set RUN_INTEGRATION_TESTS=1 to use Docker Compose services",
    ),
]


def write_pdf(file_path: Path) -> None:
    document = fitz.open()
    first_page = document.new_page()
    first_page.insert_text((72, 72), "PDF page one")
    second_page = document.new_page()
    second_page.insert_text((72, 72), "PDF page two")
    document.save(file_path)
    document.close()


def write_docx(file_path: Path, text: str) -> None:
    document = WordDocument()
    document.add_paragraph(text)
    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "Table A"
    table.cell(0, 1).text = "Table B"
    document.save(file_path)


def write_legacy_doc(file_path: Path) -> None:
    source_docx = file_path.with_suffix(".docx")
    write_docx(source_docx, "Legacy DOC content")
    with TemporaryDirectory(prefix="libreoffice-test-profile-") as profile:
        process = subprocess.run(
            [
                "soffice",
                "--headless",
                f"-env:UserInstallation={Path(profile).resolve().as_uri()}",
                "--convert-to",
                "doc:MS Word 97",
                "--outdir",
                str(file_path.parent),
                str(source_docx),
            ],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    source_docx.unlink(missing_ok=True)
    assert process.returncode == 0, process.stderr or process.stdout
    assert file_path.is_file()


def test_pdf_docx_and_doc_extraction_persist_relative_paths() -> None:
    settings = get_settings()
    client = MongoClient(settings.mongodb_uri)
    database = client.get_default_database()
    ensure_database_schema(database)
    curriculum_id = ObjectId()
    document_ids: list[ObjectId] = []
    artifact_paths: list[Path] = []

    database["curricula"].insert_one(
        {
            "_id": curriculum_id,
            "curriculumCode": "EXTRACTION-TEST",
            "curriculumName": "Extraction Test Curriculum",
            "curriculumYear": 2026,
            "version": 1,
            "status": "test",
            "sources": [],
            "timestamp": datetime.now(timezone.utc),
        }
    )

    try:
        service = DocumentExtractionService(settings, database)
        for file_type in ("pdf", "docx", "doc"):
            document_id = ObjectId()
            document_ids.append(document_id)
            original_path = (
                settings.project_data_root
                / "documents"
                / "original"
                / "cv"
                / f"{document_id}.{file_type}"
            )
            original_path.parent.mkdir(parents=True, exist_ok=True)
            artifact_paths.append(original_path)
            if file_type == "pdf":
                write_pdf(original_path)
            elif file_type == "docx":
                write_docx(original_path, "DOCX paragraph")
            else:
                write_legacy_doc(original_path)

            original_relative = PurePosixPath(
                "project-data",
                "documents",
                "original",
                "cv",
                original_path.name,
            ).as_posix()
            database["documents"].insert_one(
                {
                    "_id": document_id,
                    "documentType": "cv",
                    "fileType": file_type,
                    "fileName": f"source.{file_type}",
                    "curriculumId": curriculum_id,
                    "originalFile": {"storage": "local", "path": original_relative},
                    "convertedFile": {"storage": "local", "path": ""},
                    "extractedText": {"storage": "local", "path": ""},
                    "status": "uploaded",
                    "timestamp": datetime.now(timezone.utc),
                }
            )

            result = service.process_document(str(document_id))
            record = database["documents"].find_one({"_id": document_id})
            assert record is not None
            assert result["status"] == "processing"
            assert record["status"] == "processing"
            assert record["extractedText"]["path"].startswith(
                "project-data/documents/extracted/cv/"
            )

            extracted_relative = PurePosixPath(record["extractedText"]["path"])
            extracted_path = settings.project_data_root.joinpath(
                *extracted_relative.parts[1:]
            )
            artifact_paths.append(extracted_path)
            payload = json.loads(extracted_path.read_text(encoding="utf-8"))
            assert payload["documentId"] == str(document_id)
            assert payload["pages"][0]["pageNumber"] == 1

            if file_type == "pdf":
                assert [page["pageNumber"] for page in payload["pages"]] == [1, 2]
                assert record["convertedFile"]["path"] == ""
            elif file_type == "docx":
                assert "DOCX paragraph" in payload["pages"][0]["text"]
                assert "Table A\tTable B" in payload["pages"][0]["text"]
                assert record["convertedFile"]["path"] == ""
            else:
                assert "Legacy DOC content" in payload["pages"][0]["text"]
                assert record["convertedFile"]["path"].startswith(
                    "project-data/documents/converted/cv/"
                )
                converted_relative = PurePosixPath(record["convertedFile"]["path"])
                converted_path = settings.project_data_root.joinpath(
                    *converted_relative.parts[1:]
                )
                artifact_paths.append(converted_path)
                assert converted_path.is_file()
    finally:
        database["documents"].delete_many({"_id": {"$in": document_ids}})
        database["curricula"].delete_one({"_id": curriculum_id})
        for path in artifact_paths:
            path.unlink(missing_ok=True)
        client.close()

