"""Versioned PS template intake without document-pipeline processing."""

import io
import logging
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from bson import ObjectId
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from app.config import Settings

logger = logging.getLogger(__name__)


class TemplateValidationError(ValueError):
    """Raised when a template upload violates the v1.3 contract."""


class TemplateVersionConflictError(ValueError):
    """Raised when template_ps already contains the requested version."""


class TemplateNotFoundError(LookupError):
    """Raised when a requested template version or its file does not exist."""


class TemplateImportService:
    """Validate and persist one versioned DOCX or PDF template."""

    def __init__(self, settings: Settings, database: Database[dict[str, Any]]) -> None:
        self._settings = settings
        self._database = database

    def import_template(
        self,
        *,
        version: int,
        file_name: str | None,
        content: bytes,
    ) -> dict[str, Any]:
        safe_name = Path(file_name or "").name
        self._validate(version=version, file_name=safe_name, content=content)
        if self._database["template_ps"].find_one({"version": version}, {"_id": 1}):
            raise TemplateVersionConflictError(
                f"template version {version} already exists"
            )

        template_id = ObjectId()
        extension = Path(safe_name).suffix.lower()
        relative_path = PurePosixPath(
            "project-data",
            "documents",
            "original",
            "template",
            f"{template_id}{extension}",
        )
        target_path = self._target_path(relative_path.name)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with target_path.open("xb") as destination:
                destination.write(content)
        except Exception:
            logger.exception("Template file storage failed templateId=%s", template_id)
            raise

        timestamp = datetime.now(timezone.utc)
        record = {
            "_id": template_id,
            "version": version,
            "fileName": safe_name,
            "fileType": extension.removeprefix("."),
            "originalFile": {
                "storage": "local",
                "path": relative_path.as_posix(),
            },
            "timestamp": timestamp,
        }
        try:
            self._database["template_ps"].insert_one(record)
        except DuplicateKeyError as exc:
            target_path.unlink(missing_ok=True)
            raise TemplateVersionConflictError(
                f"template version {version} already exists"
            ) from exc
        except Exception:
            target_path.unlink(missing_ok=True)
            logger.exception("Template MongoDB write failed templateId=%s", template_id)
            raise

        logger.info(
            "Template stored templateId=%s version=%s path=%s",
            template_id,
            version,
            relative_path,
        )
        return {
            "templateId": str(template_id),
            "version": version,
            "fileName": safe_name,
            "fileType": extension.removeprefix("."),
            "originalFile": record["originalFile"],
            "timestamp": timestamp,
        }

    def get_template_file(self, version: int) -> tuple[Path, str]:
        if version < 1:
            raise TemplateNotFoundError(f"template version {version} was not found")
        record = self._database["template_ps"].find_one(
            {"version": version},
            {"fileName": 1, "originalFile": 1},
        )
        if record is None:
            raise TemplateNotFoundError(f"template version {version} was not found")

        stored_path = PurePosixPath(record["originalFile"]["path"])
        if (
            stored_path.is_absolute()
            or not stored_path.parts
            or stored_path.parts[0] != "project-data"
        ):
            raise TemplateNotFoundError("template file path is invalid")

        root = self._settings.project_data_root.resolve()
        target = root.joinpath(*stored_path.parts[1:]).resolve()
        if not target.is_relative_to(root) or target.suffix.lower() not in {".docx", ".pdf"}:
            raise TemplateNotFoundError("template file path is invalid")
        if not target.is_file():
            raise TemplateNotFoundError(f"template version {version} file was not found")
        return target, Path(record["fileName"]).name

    @staticmethod
    def _validate(*, version: int, file_name: str, content: bytes) -> None:
        if version < 1:
            raise TemplateValidationError("version must be a positive integer")
        extension = Path(file_name).suffix.lower()
        if not file_name or extension not in {".docx", ".pdf"}:
            raise TemplateValidationError("template must be a DOCX or PDF file")
        if not content:
            raise TemplateValidationError("template file must not be empty")
        if extension == ".pdf":
            if not content.startswith(b"%PDF-") or b"%%EOF" not in content[-1024:]:
                raise TemplateValidationError("template is not a readable PDF file")
            return
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as package:
                if "word/document.xml" not in package.namelist():
                    raise TemplateValidationError("template is not a readable DOCX file")
                if package.testzip() is not None:
                    raise TemplateValidationError("template DOCX package is corrupted")
        except zipfile.BadZipFile as exc:
            raise TemplateValidationError("template is not a readable DOCX file") from exc

    def _target_path(self, file_name: str) -> Path:
        root = self._settings.project_data_root.resolve()
        target = (root / "documents" / "original" / "template" / file_name).resolve()
        if not target.is_relative_to(root):
            raise ValueError("Resolved template path is outside PROJECT_DATA_ROOT")
        return target
