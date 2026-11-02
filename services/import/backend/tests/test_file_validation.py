from io import BytesIO
from zipfile import ZipFile

import fitz
import pytest

from app.services.file_validation import (
    DocumentValidationError,
    sanitize_file_name,
    validate_upload,
)


def make_pdf() -> bytes:
    document = fitz.open()
    document.new_page()
    content = document.tobytes()
    document.close()
    return content


def make_docx() -> bytes:
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
        archive.writestr("word/document.xml", "<document />")
    return output.getvalue()


def make_doc() -> bytes:
    content = bytearray(512)
    content[:8] = bytes.fromhex("D0CF11E0A1B11AE1")
    content[28:30] = b"\xfe\xff"
    content[30:32] = (9).to_bytes(2, "little")
    return bytes(content)


@pytest.mark.parametrize(
    ("file_name", "content_type", "content", "expected_extension"),
    [
        ("sample.pdf", "application/pdf", make_pdf(), ".pdf"),
        (
            "sample.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            make_docx(),
            ".docx",
        ),
        ("sample.doc", "application/msword", make_doc(), ".doc"),
    ],
)
def test_supported_files_are_validated(
    file_name: str,
    content_type: str,
    content: bytes,
    expected_extension: str,
) -> None:
    result = validate_upload(
        document_type="cv",
        file_name=file_name,
        content_type=content_type,
        content=content,
    )

    assert result.extension == expected_extension
    assert result.document_type == "cv"


def test_client_path_is_removed_from_file_name() -> None:
    assert sanitize_file_name(r"C:\Users\person\teacher.pdf") == "teacher.pdf"


@pytest.mark.parametrize(
    ("document_type", "file_name", "content_type", "content"),
    [
        ("report", "sample.pdf", "application/pdf", b"not-a-pdf"),
        ("cv", "sample.txt", "text/plain", b"text"),
        ("cv", "sample.pdf", "application/pdf", b""),
        ("cv", "sample.pdf", "application/msword", b"not-a-pdf"),
        ("cv", "sample.pdf", "application/pdf", b"not-a-pdf"),
        (
            "cv",
            "sample.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            b"not-a-docx",
        ),
        ("cv", "sample.doc", "application/msword", b"not-a-doc"),
    ],
)
def test_invalid_uploads_are_rejected(
    document_type: str,
    file_name: str,
    content_type: str,
    content: bytes,
) -> None:
    with pytest.raises(DocumentValidationError):
        validate_upload(
            document_type=document_type,
            file_name=file_name,
            content_type=content_type,
            content=content,
        )

