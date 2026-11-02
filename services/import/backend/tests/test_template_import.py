import io
import zipfile
from pathlib import Path
from typing import Any

import pytest

from app.config import Settings
from app.services.template_import import (
    TemplateImportService,
    TemplateNotFoundError,
    TemplateValidationError,
    TemplateVersionConflictError,
)


class FakeCollection:
    def __init__(self) -> None:
        self.documents: list[dict[str, Any]] = []

    def find_one(self, query: dict[str, Any], projection: dict[str, int]) -> dict[str, Any] | None:
        return next(
            (item for item in self.documents if item.get("version") == query["version"]),
            None,
        )

    def insert_one(self, document: dict[str, Any]) -> None:
        self.documents.append(document)


class FakeDatabase:
    def __init__(self) -> None:
        self.collection = FakeCollection()

    def __getitem__(self, name: str) -> FakeCollection:
        assert name == "template_ps"
        return self.collection


def valid_docx() -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as package:
        package.writestr("word/document.xml", "<document />")
    return stream.getvalue()


def valid_pdf() -> bytes:
    return b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\n%%EOF\n"


def test_template_is_stored_with_version_relative_path_and_timestamp(tmp_path: Path) -> None:
    database = FakeDatabase()
    content = valid_docx()
    service = TemplateImportService(
        Settings(project_data_root=tmp_path),
        database,  # type: ignore[arg-type]
    )

    response = service.import_template(
        version=1,
        file_name="template.docx",
        content=content,
    )

    [record] = database.collection.documents
    assert set(record) == {
        "_id", "version", "fileName", "fileType", "originalFile", "timestamp"
    }
    assert record["version"] == 1
    assert record["fileType"] == "docx"
    assert record["originalFile"]["path"].startswith(
        "project-data/documents/original/template/"
    )
    stored = tmp_path / "documents" / "original" / "template" / Path(
        record["originalFile"]["path"]
    ).name
    assert stored.read_bytes() == content
    assert response["templateId"] == str(record["_id"])


def test_duplicate_template_version_is_rejected_without_writing_file(tmp_path: Path) -> None:
    database = FakeDatabase()
    database.collection.documents.append({"version": 1})
    service = TemplateImportService(
        Settings(project_data_root=tmp_path),
        database,  # type: ignore[arg-type]
    )

    with pytest.raises(TemplateVersionConflictError):
        service.import_template(version=1, file_name="template.docx", content=valid_docx())

    assert list(tmp_path.rglob("*.docx")) == []


def test_stored_template_can_be_resolved_for_download(tmp_path: Path) -> None:
    database = FakeDatabase()
    service = TemplateImportService(
        Settings(project_data_root=tmp_path),
        database,  # type: ignore[arg-type]
    )
    service.import_template(
        version=2,
        file_name="PS template.docx",
        content=valid_docx(),
    )

    path, download_name = service.get_template_file(2)

    assert path.is_file()
    assert path.is_relative_to(tmp_path)
    assert download_name == "PS template.docx"


def test_pdf_template_is_stored_and_resolved_for_download(tmp_path: Path) -> None:
    database = FakeDatabase()
    service = TemplateImportService(
        Settings(project_data_root=tmp_path),
        database,  # type: ignore[arg-type]
    )
    response = service.import_template(
        version=3,
        file_name="PS template.pdf",
        content=valid_pdf(),
    )

    path, download_name = service.get_template_file(3)

    assert response["fileType"] == "pdf"
    assert path.suffix == ".pdf"
    assert path.read_bytes() == valid_pdf()
    assert download_name == "PS template.pdf"


def test_download_rejects_missing_version_and_unsafe_path(tmp_path: Path) -> None:
    database = FakeDatabase()
    service = TemplateImportService(
        Settings(project_data_root=tmp_path),
        database,  # type: ignore[arg-type]
    )
    with pytest.raises(TemplateNotFoundError):
        service.get_template_file(99)

    database.collection.documents.append(
        {
            "version": 3,
            "fileName": "unsafe.docx",
            "originalFile": {"storage": "local", "path": "../unsafe.docx"},
        }
    )
    with pytest.raises(TemplateNotFoundError, match="path is invalid"):
        service.get_template_file(3)


@pytest.mark.parametrize(
    ("version", "file_name", "content"),
    [
        (0, "template.docx", b"data"),
        (1, "template.pdf", b"data"),
        (1, "template.docx", b""),
        (1, "template.docx", b"not-a-docx"),
    ],
)
def test_invalid_template_is_rejected(
    tmp_path: Path,
    version: int,
    file_name: str,
    content: bytes,
) -> None:
    service = TemplateImportService(
        Settings(project_data_root=tmp_path),
        FakeDatabase(),  # type: ignore[arg-type]
    )

    with pytest.raises(TemplateValidationError):
        service.import_template(version=version, file_name=file_name, content=content)
