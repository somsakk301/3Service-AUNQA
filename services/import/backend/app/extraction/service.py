"""Phase 4 document conversion, extraction, storage, and status updates."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from pymongo.database import Database

from app.config import Settings
from app.extraction.converter import convert_doc_to_docx
from app.extraction.docx import extract_docx
from app.extraction.models import ExtractedPage
from app.extraction.pdf import extract_pdf

logger = logging.getLogger(__name__)


class DocumentExtractionError(RuntimeError):
    """Raised when a document record or source file cannot be processed."""


class DocumentExtractionService:
    """Execute SRS processing steps 05-06 for one documents record."""

    def __init__(self, settings: Settings, database: Database[dict[str, Any]]) -> None:
        self._settings = settings
        self._database = database

    def process_document(self, document_id: str) -> dict[str, Any]:
        object_id = self._parse_document_id(document_id)
        document = self._database["documents"].find_one({"_id": object_id})
        if document is None:
            raise DocumentExtractionError("Document record was not found")

        self._database["documents"].update_one(
            {"_id": object_id},
            {"$set": {"status": "processing", "timestamp": self._now()}},
        )
        logger.info("Extraction started documentId=%s", object_id)

        converted_path: Path | None = None
        extracted_path: Path | None = None
        try:
            original_path = self._resolve_relative_path(
                document["originalFile"]["path"],
                expected_area="original",
                document_type=document["documentType"],
            )
            if not original_path.is_file():
                raise DocumentExtractionError("Original file does not exist")

            file_type = document["fileType"]
            converted_relative = ""
            if file_type == "pdf":
                pages = extract_pdf(original_path)
            elif file_type == "docx":
                pages = extract_docx(original_path)
            elif file_type == "doc":
                converted_directory = (
                    self._settings.project_data_root
                    / "documents"
                    / "converted"
                    / document["documentType"]
                )
                converted_path = convert_doc_to_docx(
                    original_path,
                    converted_directory,
                )
                converted_relative = self._relative_project_path(converted_path)
                pages = extract_docx(converted_path)
            else:
                raise DocumentExtractionError("Unsupported documents.fileType")

            extracted_path = (
                self._settings.project_data_root
                / "documents"
                / "extracted"
                / document["documentType"]
                / f"{object_id}.json"
            )
            self._write_extracted_json(
                extracted_path,
                document_id=str(object_id),
                document_type=document["documentType"],
                pages=pages,
            )
            extracted_relative = self._relative_project_path(extracted_path)

            timestamp = self._now()
            self._database["documents"].update_one(
                {"_id": object_id},
                {
                    "$set": {
                        "convertedFile": {
                            "storage": "local",
                            "path": converted_relative,
                        },
                        "extractedText": {
                            "storage": "local",
                            "path": extracted_relative,
                        },
                        "status": "processing",
                        "timestamp": timestamp,
                    }
                },
            )
            logger.info(
                "Extraction completed documentId=%s pages=%s",
                object_id,
                len(pages),
            )
            return {
                "documentId": str(object_id),
                "convertedFile": converted_relative,
                "extractedText": extracted_relative,
                "pageCount": len(pages),
                "status": "processing",
            }
        except Exception:
            if extracted_path is not None:
                extracted_path.unlink(missing_ok=True)
            if converted_path is not None:
                converted_path.unlink(missing_ok=True)
            self._database["documents"].update_one(
                {"_id": object_id},
                {"$set": {"status": "failed", "timestamp": self._now()}},
            )
            logger.exception("Extraction failed documentId=%s", object_id)
            raise

    @staticmethod
    def _parse_document_id(document_id: str) -> ObjectId:
        try:
            return ObjectId(document_id)
        except (InvalidId, TypeError) as exc:
            raise DocumentExtractionError("documentId must be a valid ObjectId") from exc

    def _resolve_relative_path(
        self,
        relative_path: str,
        *,
        expected_area: str,
        document_type: str,
    ) -> Path:
        path = PurePosixPath(relative_path)
        expected_prefix = (
            "project-data",
            "documents",
            expected_area,
            document_type,
        )
        if path.is_absolute() or path.parts[:4] != expected_prefix:
            raise DocumentExtractionError("Stored document path is invalid")
        target = self._settings.project_data_root.joinpath(*path.parts[1:]).resolve()
        root = self._settings.project_data_root.resolve()
        if not target.is_relative_to(root):
            raise DocumentExtractionError("Stored document path escapes PROJECT_DATA_ROOT")
        return target

    def _relative_project_path(self, file_path: Path) -> str:
        root = self._settings.project_data_root.resolve()
        resolved = file_path.resolve()
        if not resolved.is_relative_to(root):
            raise DocumentExtractionError("Generated path escapes PROJECT_DATA_ROOT")
        inside_root = resolved.relative_to(root)
        return PurePosixPath("project-data", *inside_root.parts).as_posix()

    @staticmethod
    def _write_extracted_json(
        file_path: Path,
        *,
        document_id: str,
        document_type: str,
        pages: list[ExtractedPage],
    ) -> None:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = file_path.with_suffix(".json.tmp")
        payload = {
            "documentId": document_id,
            "documentType": document_type,
            "pages": [page.to_dict() for page in pages],
        }
        try:
            temporary_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            temporary_path.replace(file_path)
        finally:
            temporary_path.unlink(missing_ok=True)

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

