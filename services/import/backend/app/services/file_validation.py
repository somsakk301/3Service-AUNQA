"""Validation for files accepted by the locked Import Service SRS."""

from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePosixPath
from zipfile import BadZipFile, ZipFile

import fitz

SUPPORTED_DOCUMENT_TYPES = frozenset({"curriculum", "cv", "appointment"})
SUPPORTED_EXTENSIONS = frozenset({".pdf", ".doc", ".docx"})
ALLOWED_CONTENT_TYPES = {
    ".pdf": frozenset({"application/pdf"}),
    ".doc": frozenset({"application/msword"}),
    ".docx": frozenset(
        {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
    ),
}

_OLE_COMPOUND_FILE_SIGNATURE = bytes.fromhex("D0CF11E0A1B11AE1")


class DocumentValidationError(ValueError):
    """Raised when an uploaded document violates an SRS validation rule."""


@dataclass(frozen=True)
class ValidatedUpload:
    document_type: str
    file_name: str
    extension: str
    content: bytes


def sanitize_file_name(file_name: str | None) -> str:
    """Discard client-side path components and return a safe base name."""

    if not file_name or "\x00" in file_name:
        raise DocumentValidationError("A valid file name is required")
    normalized = file_name.replace("\\", "/")
    safe_name = PurePosixPath(normalized).name
    if safe_name in {"", ".", ".."}:
        raise DocumentValidationError("A valid file name is required")
    return safe_name


def validate_upload(
    *,
    document_type: str,
    file_name: str | None,
    content_type: str | None,
    content: bytes,
) -> ValidatedUpload:
    """Validate metadata, declared MIME type, size, and file structure."""

    normalized_document_type = document_type.strip().lower()
    if normalized_document_type not in SUPPORTED_DOCUMENT_TYPES:
        raise DocumentValidationError(
            "documentType must be curriculum, cv, or appointment"
        )

    safe_name = sanitize_file_name(file_name)
    extension = PurePosixPath(safe_name).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise DocumentValidationError("Only .pdf, .doc, and .docx files are supported")

    if content_type not in ALLOWED_CONTENT_TYPES[extension]:
        raise DocumentValidationError("File MIME type does not match its extension")

    if len(content) == 0:
        raise DocumentValidationError("File size must be greater than zero")

    if extension == ".pdf":
        _validate_pdf(content)
    elif extension == ".docx":
        _validate_docx(content)
    else:
        _validate_doc(content)

    return ValidatedUpload(
        document_type=normalized_document_type,
        file_name=safe_name,
        extension=extension,
        content=content,
    )


def _validate_pdf(content: bytes) -> None:
    try:
        with fitz.open(stream=content, filetype="pdf") as document:
            if document.needs_pass or document.page_count < 1:
                raise DocumentValidationError("PDF is encrypted, empty, or unreadable")
            document.load_page(0)
    except DocumentValidationError:
        raise
    except Exception as exc:
        raise DocumentValidationError("PDF is corrupt or unreadable") from exc


def _validate_docx(content: bytes) -> None:
    try:
        with ZipFile(BytesIO(content)) as archive:
            names = set(archive.namelist())
            if archive.testzip() is not None:
                raise DocumentValidationError("DOCX archive contains corrupt data")
            required_parts = {"[Content_Types].xml", "word/document.xml"}
            if not required_parts.issubset(names):
                raise DocumentValidationError("DOCX structure is incomplete")
    except DocumentValidationError:
        raise
    except (BadZipFile, OSError) as exc:
        raise DocumentValidationError("DOCX is corrupt or unreadable") from exc


def _validate_doc(content: bytes) -> None:
    # Legacy DOC is an OLE Compound File. Full conversion/readability validation
    # remains the responsibility of the SRS-defined LibreOffice conversion step.
    if len(content) < 512 or not content.startswith(_OLE_COMPOUND_FILE_SIGNATURE):
        raise DocumentValidationError("DOC is corrupt or unreadable")
    if content[28:30] != b"\xfe\xff":
        raise DocumentValidationError("DOC has an invalid OLE byte order")
    sector_shift = int.from_bytes(content[30:32], "little")
    if sector_shift not in {9, 12}:
        raise DocumentValidationError("DOC has an invalid OLE sector size")

