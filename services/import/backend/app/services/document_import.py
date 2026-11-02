"""Document intake orchestration through status=uploaded."""

import logging
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from pymongo.database import Database

from app.config import Settings
from app.services.file_validation import ValidatedUpload

logger = logging.getLogger(__name__)


class CurriculumReferenceError(ValueError):
    """Raised when curriculumId is invalid or does not reference curricula._id."""


class DocumentFileNotFoundError(ValueError):
    """Raised when an imported document or its safely resolved original file is unavailable."""


class DocumentImportService:
    """Store an original file and create its exact SRS document record."""

    def __init__(self, settings: Settings, database: Database[dict[str, Any]]) -> None:
        self._settings = settings
        self._database = database

    def import_document(
        self,
        *,
        upload: ValidatedUpload,
        curriculum_id: str,
        document_id: ObjectId | None = None,
    ) -> dict[str, Any]:
        curriculum_object_id = self._validate_curriculum_reference(
            curriculum_id,
            allow_missing=upload.document_type == "curriculum",
        )
        document_id = document_id or ObjectId()
        if self._database["documents"].find_one({"_id": document_id}, {"_id": 1}):
            raise ValueError("Preview documentId already exists")
        relative_path = PurePosixPath(
            "project-data",
            "documents",
            "original",
            upload.document_type,
            f"{document_id}{upload.extension}",
        )
        target_path = self._target_path(upload.document_type, relative_path.name)

        logger.info(
            "Original file storage started documentId=%s documentType=%s",
            document_id,
            upload.document_type,
        )
        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with target_path.open("xb") as destination:
                destination.write(upload.content)
        except Exception:
            logger.exception(
                "Original file storage failed documentId=%s", document_id
            )
            raise

        timestamp = datetime.now(timezone.utc)
        document_record = {
            "_id": document_id,
            "documentType": upload.document_type,
            "fileType": upload.extension.removeprefix("."),
            "fileName": upload.file_name,
            "curriculumId": curriculum_object_id,
            "originalFile": {
                "storage": "local",
                "path": relative_path.as_posix(),
            },
            "convertedFile": {
                "storage": "local",
                "path": "",
            },
            "extractedText": {
                "storage": "local",
                "path": "",
            },
            "status": "uploaded",
            "timestamp": timestamp,
        }

        try:
            self._database["documents"].insert_one(document_record)
        except Exception:
            target_path.unlink(missing_ok=True)
            logger.exception("MongoDB write failed documentId=%s", document_id)
            raise

        logger.info(
            "MongoDB documents write completed documentId=%s status=uploaded",
            document_id,
        )
        return {
            "documentId": str(document_id),
            "documentType": upload.document_type,
            "fileType": upload.extension.removeprefix("."),
            "fileName": upload.file_name,
            "curriculumId": str(curriculum_object_id),
            "originalFile": document_record["originalFile"],
            "status": "uploaded",
            "timestamp": timestamp,
        }

    def _validate_curriculum_reference(
        self,
        curriculum_id: str,
        *,
        allow_missing: bool = False,
    ) -> ObjectId:
        try:
            curriculum_object_id = ObjectId(curriculum_id)
        except (InvalidId, TypeError) as exc:
            raise CurriculumReferenceError(
                "curriculumId must be a valid ObjectId"
            ) from exc

        curriculum = self._database["curricula"].find_one(
            {"_id": curriculum_object_id},
            {"_id": 1},
        )
        if curriculum is None and not allow_missing:
            raise CurriculumReferenceError(
                "curriculumId must reference an existing curricula._id"
            )
        return curriculum_object_id

    def _target_path(self, document_type: str, file_name: str) -> Path:
        root = self._settings.project_data_root.resolve()
        target = (root / "documents" / "original" / document_type / file_name).resolve()
        if not target.is_relative_to(root):
            raise ValueError("Resolved storage path is outside PROJECT_DATA_ROOT")
        return target

    def get_original_file(self, document_id: str) -> tuple[Path, str]:
        """Resolve an imported document's original file without trusting a client path."""

        try:
            object_id = ObjectId(document_id)
        except (InvalidId, TypeError) as exc:
            raise DocumentFileNotFoundError("Document was not found") from exc

        document = self._database["documents"].find_one(
            {"_id": object_id},
            {"fileName": 1, "originalFile": 1},
        )
        if document is None:
            raise DocumentFileNotFoundError("Document was not found")

        original = document.get("originalFile")
        original = original if isinstance(original, dict) else {}
        stored_path = original.get("path")
        if original.get("storage") != "local" or not isinstance(stored_path, str):
            raise DocumentFileNotFoundError("Original file is unavailable")

        relative_path = PurePosixPath(stored_path)
        expected_prefix = ("project-data", "documents", "original")
        if relative_path.is_absolute() or relative_path.parts[:3] != expected_prefix:
            raise DocumentFileNotFoundError("Original file path is invalid")

        root = self._settings.project_data_root.resolve()
        target = root.joinpath(*relative_path.parts[1:]).resolve()
        if not target.is_relative_to(root) or not target.is_file():
            raise DocumentFileNotFoundError("Original file is unavailable")

        file_name = document.get("fileName")
        return target, file_name if isinstance(file_name, str) and file_name else target.name

