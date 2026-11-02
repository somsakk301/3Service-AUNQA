from pathlib import Path
from typing import Any

import pytest
from bson import ObjectId

from app.config import Settings
from app.services.document_import import (
    CurriculumReferenceError,
    DocumentFileNotFoundError,
    DocumentImportService,
)
from app.services.file_validation import ValidatedUpload


class FakeCollection:
    def __init__(self, documents: list[dict[str, Any]] | None = None) -> None:
        self.documents = documents or []
        self.fail_insert = False

    def find_one(
        self, query: dict[str, Any], projection: dict[str, int]
    ) -> dict[str, Any] | None:
        return next(
            (document for document in self.documents if document["_id"] == query["_id"]),
            None,
        )

    def insert_one(self, document: dict[str, Any]) -> None:
        if self.fail_insert:
            raise RuntimeError("insert failed")
        self.documents.append(document)


class FakeDatabase:
    def __init__(self, curriculum_id: ObjectId) -> None:
        self.collections = {
            "curricula": FakeCollection([{"_id": curriculum_id}]),
            "documents": FakeCollection(),
        }

    def __getitem__(self, name: str) -> FakeCollection:
        return self.collections[name]


def make_upload() -> ValidatedUpload:
    return ValidatedUpload(
        document_type="cv",
        file_name="teacher.pdf",
        extension=".pdf",
        content=b"validated-content",
    )


def test_original_file_and_document_record_follow_srs(tmp_path: Path) -> None:
    curriculum_id = ObjectId()
    database = FakeDatabase(curriculum_id)
    settings = Settings(project_data_root=tmp_path)
    service = DocumentImportService(settings, database)  # type: ignore[arg-type]

    response = service.import_document(
        upload=make_upload(),
        curriculum_id=str(curriculum_id),
    )

    records = database["documents"].documents
    assert len(records) == 1
    record = records[0]
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
    assert not Path(record["originalFile"]["path"]).is_absolute()
    assert record["originalFile"]["path"].startswith(
        "project-data/documents/original/cv/"
    )
    stored_file = tmp_path / "documents" / "original" / "cv" / Path(
        record["originalFile"]["path"]
    ).name
    assert stored_file.read_bytes() == b"validated-content"
    assert response["documentId"] == str(record["_id"])


def test_missing_curriculum_reference_is_rejected(tmp_path: Path) -> None:
    database = FakeDatabase(ObjectId())
    service = DocumentImportService(
        Settings(project_data_root=tmp_path),
        database,  # type: ignore[arg-type]
    )

    with pytest.raises(CurriculumReferenceError):
        service.import_document(upload=make_upload(), curriculum_id=str(ObjectId()))

    assert list(tmp_path.rglob("*.pdf")) == []
    assert database["documents"].documents == []


def test_file_is_removed_when_mongodb_insert_fails(tmp_path: Path) -> None:
    curriculum_id = ObjectId()
    database = FakeDatabase(curriculum_id)
    database["documents"].fail_insert = True
    service = DocumentImportService(
        Settings(project_data_root=tmp_path),
        database,  # type: ignore[arg-type]
    )

    with pytest.raises(RuntimeError, match="insert failed"):
        service.import_document(
            upload=make_upload(),
            curriculum_id=str(curriculum_id),
        )

    assert list(tmp_path.rglob("*.pdf")) == []


def test_imported_original_file_can_be_resolved_for_inline_view(tmp_path: Path) -> None:
    curriculum_id = ObjectId()
    database = FakeDatabase(curriculum_id)
    service = DocumentImportService(
        Settings(project_data_root=tmp_path),
        database,  # type: ignore[arg-type]
    )
    response = service.import_document(upload=make_upload(), curriculum_id=str(curriculum_id))

    path, file_name = service.get_original_file(response["documentId"])

    assert path.read_bytes() == b"validated-content"
    assert file_name == "teacher.pdf"


def test_original_file_resolution_rejects_unknown_or_unsafe_documents(tmp_path: Path) -> None:
    database = FakeDatabase(ObjectId())
    service = DocumentImportService(
        Settings(project_data_root=tmp_path),
        database,  # type: ignore[arg-type]
    )

    with pytest.raises(DocumentFileNotFoundError):
        service.get_original_file(str(ObjectId()))

    unsafe_id = ObjectId()
    database["documents"].documents.append({
        "_id": unsafe_id,
        "fileName": "unsafe.pdf",
        "originalFile": {"storage": "local", "path": "project-data/../../unsafe.pdf"},
    })
    with pytest.raises(DocumentFileNotFoundError):
        service.get_original_file(str(unsafe_id))

