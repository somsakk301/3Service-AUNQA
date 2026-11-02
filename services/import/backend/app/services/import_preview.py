"""Read-only Preview/Edit/Confirm preparation for document imports."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from collections.abc import Iterable, Mapping

from bson import ObjectId
from bson.errors import InvalidId
from pymongo.database import Database

from app.chunking import DocumentChunker
from app.config import Settings
from app.extraction.converter import convert_doc_to_docx
from app.extraction.docx import extract_docx
from app.extraction.models import ExtractedPage
from app.extraction.pdf import extract_pdf
from app.parsing import (
    parse_appointments,
    parse_curriculum,
    parse_curriculum_people,
    parse_cv,
)
from app.parsing.normalization import normalize_person_name
from app.parsing.models import (
    AcademicWorkData,
    AppointmentData,
    CurriculumData,
    EducationData,
    PersonData,
)
from app.persistence import preview_source, validate_sources
from app.services.file_validation import ValidatedUpload


class ImportPreviewError(ValueError):
    """Raised when a file cannot produce a safe, confirmable preview."""


class ImportPreviewService:
    """Extract and parse an upload without writing MongoDB or ChromaDB."""

    def __init__(
        self,
        settings: Settings,
        database: Database[dict[str, Any]],
    ) -> None:
        self._settings = settings
        self._database = database
        self._chunker = DocumentChunker(settings)

    def preview(
        self,
        *,
        upload: ValidatedUpload,
        curriculum_id: str | None,
        curriculum_version: int | None = None,
        curriculum_status: str | None = None,
    ) -> dict[str, Any]:
        preview_id = ObjectId()
        pages = self._extract(upload)
        text = "\n".join(page.text for page in pages)
        if upload.document_type == "curriculum":
            if curriculum_version is None or curriculum_version < 1:
                raise ImportPreviewError(
                    "curriculumVersion must be a positive integer"
                )
            if not curriculum_status or not curriculum_status.strip():
                raise ImportPreviewError("curriculumStatus is required")
            curriculum = parse_curriculum(
                text,
                reference={
                    "version": curriculum_version,
                    "status": curriculum_status,
                },
            ).model_dump()
            existing = self._database["curricula"].find_one(
                {
                    "curriculumCode": curriculum["curriculumCode"],
                    "curriculumYear": curriculum["curriculumYear"],
                    "version": curriculum["version"],
                },
                {"_id": 1},
            )
            curriculum_object_id = existing["_id"] if existing else ObjectId()
        else:
            if curriculum_id is None:
                raise ImportPreviewError("curriculumId is required")
            curriculum_object_id, curriculum = self._curriculum(curriculum_id)
        collections = self._parse_collections(
            upload.document_type,
            text,
            curriculum_id=curriculum_object_id,
            curriculum=curriculum,
            source_document_id=preview_id,
        )
        chunks = self._chunker.chunk_document(
            document_id=preview_id,
            curriculum_id=curriculum_object_id,
            document_type=upload.document_type,
            pages=pages,
        )
        return {
            "previewId": str(preview_id),
            "documentType": upload.document_type,
            "fileType": upload.extension.removeprefix("."),
            "fileName": upload.file_name,
            "curriculumId": str(curriculum_object_id),
            "collections": collections,
            "systemPreview": {
                "documents": [
                    {
                        "_id": str(preview_id),
                        "documentType": upload.document_type,
                        "fileType": upload.extension.removeprefix("."),
                        "fileName": upload.file_name,
                        "curriculumId": str(curriculum_object_id),
                        "originalFile": {
                            "storage": "local",
                            "path": (
                                "project-data/documents/original/"
                                f"{upload.document_type}/{preview_id}{upload.extension}"
                            ),
                        },
                        "status": "uploaded after confirmation",
                    }
                ],
                "data_usages": self._usage_preview(
                    collections,
                    curriculum_id=str(curriculum_object_id),
                ),
            },
            "chunks": [chunk.to_dict() for chunk in chunks],
        }

    def validate_confirmation(
        self,
        *,
        upload: ValidatedUpload,
        curriculum_id: str,
        payload: Mapping[str, Any],
    ) -> None:
        """Validate every editable value before the first persistent write."""

        if upload.document_type == "curriculum":
            try:
                curriculum_object_id = ObjectId(curriculum_id)
            except (InvalidId, TypeError) as exc:
                raise ImportPreviewError(
                    "curriculumId must be a valid ObjectId"
                ) from exc
            curriculum = self._database["curricula"].find_one(
                {"_id": curriculum_object_id}
            )
        else:
            curriculum_object_id, curriculum = self._curriculum(curriculum_id)
        preview_document_id = payload.get("previewId")
        collections = payload.get("collections")
        expected = {
            "curricula",
            "persons",
            "educations",
            "academic_works",
            "appointments",
        }
        if not isinstance(collections, Mapping) or set(collections) != expected:
            raise ImportPreviewError("Confirmed Preview collection names are invalid")
        if any(not isinstance(collections[name], list) for name in expected):
            raise ImportPreviewError("Confirmed Preview records must be arrays")

        document_type = upload.document_type
        if document_type == "curriculum":
            if len(collections["curricula"]) != 1:
                raise ImportPreviewError(
                    "Curriculum Preview must contain exactly one curricula record"
                )
            curriculum_record = collections["curricula"][0]
            self._validated_record_sources(
                curriculum_record,
                preview_document_id,
                "curricula",
                {"curriculumCode", "curriculumName", "curriculumYear"},
            )
            parsed = CurriculumData.model_validate(self._without_sources(curriculum_record))
            if curriculum is not None and (
                parsed.curriculumCode,
                parsed.curriculumYear,
                parsed.version,
            ) != (
                curriculum["curriculumCode"],
                curriculum["curriculumYear"],
                curriculum["version"],
            ):
                raise ImportPreviewError(
                    "Edited curriculum does not match the selected curriculum"
                )
            persons = []
            for item in collections["persons"]:
                values = self._without_sources(item)
                self._validated_record_sources(
                    item, preview_document_id, "persons", values.keys()
                )
                persons.append(PersonData.model_validate(values))
            for item in collections["educations"]:
                self._validate_person_index(item, len(persons))
                self._validated_record_sources(
                    item,
                    preview_document_id,
                    "educations",
                    {"personId", "degree", "field", "institution", "graduationYear"},
                )
                EducationData.model_validate(self._without_link_and_sources(item))
            if collections["academic_works"] or collections["appointments"]:
                raise ImportPreviewError(
                    "Curriculum Preview contains unsupported collection records"
                )
        elif document_type == "cv":
            if len(collections["persons"]) != 1:
                raise ImportPreviewError(
                    "CV Preview must contain exactly one persons record"
                )
            person_record = collections["persons"][0]
            person_values = self._without_sources(person_record)
            self._validated_record_sources(
                person_record, preview_document_id, "persons", person_values.keys()
            )
            PersonData.model_validate(person_values)
            for item in collections["educations"]:
                self._validate_person_index(item, 1)
                self._validated_record_sources(
                    item,
                    preview_document_id,
                    "educations",
                    {"personId", "degree", "field", "institution", "graduationYear"},
                )
                EducationData.model_validate(self._without_link_and_sources(item))
            for item in collections["academic_works"]:
                self._validate_person_index(item, 1)
                self._validated_record_sources(
                    item,
                    preview_document_id,
                    "academic_works",
                    {
                        "personId",
                        "workType",
                        "title",
                        "publicationYear",
                        "database",
                        "quartile",
                    },
                )
                AcademicWorkData.model_validate(self._without_link_and_sources(item))
            if collections["curricula"] or collections["appointments"]:
                raise ImportPreviewError("CV Preview contains unsupported records")
        elif document_type == "appointment":
            if any(
                collections[name]
                for name in ("curricula", "persons", "educations", "academic_works")
            ):
                raise ImportPreviewError(
                    "Appointment Preview contains unsupported collection records"
                )
            if not collections["appointments"]:
                raise ImportPreviewError(
                    "Appointment Preview must contain at least one appointment"
                )
            for item in collections["appointments"]:
                if not isinstance(item, Mapping):
                    raise ImportPreviewError("Appointment Preview record is invalid")
                try:
                    item_curriculum_id = ObjectId(item.get("curriculumId"))
                    person_id = ObjectId(item.get("personId"))
                except (InvalidId, TypeError) as exc:
                    raise ImportPreviewError(
                        "Appointment Preview relationships must be ObjectIds"
                    ) from exc
                if item_curriculum_id != curriculum_object_id:
                    raise ImportPreviewError(
                        "Appointment Preview curriculumId cannot be changed"
                    )
                if self._database["persons"].find_one({"_id": person_id}, {"_id": 1}) is None:
                    raise ImportPreviewError(
                        "Appointment Preview personId was not found"
                    )
                self._validated_record_sources(
                    item,
                    preview_document_id,
                    "appointments",
                    {
                        "curriculumId",
                        "personId",
                        "role",
                        "roleName",
                        "effectiveDate",
                        "appointmentOrder.orderNumber",
                        "appointmentOrder.orderDate",
                        "status",
                    },
                )
                AppointmentData.model_validate(
                    {
                        key: value
                        for key, value in item.items()
                        if key not in {"curriculumId", "personId", "sources"}
                    }
                )
        else:
            raise ImportPreviewError("Unsupported documentType for confirmation")

        pages = self._extract(upload)
        page_numbers = {page.pageNumber for page in pages}
        chunks = payload.get("chunks")
        if not isinstance(chunks, list) or not chunks:
            raise ImportPreviewError("Confirmed Preview must contain at least one chunk")
        keys: set[tuple[int, int]] = set()
        for chunk in chunks:
            if not isinstance(chunk, Mapping) or not isinstance(chunk.get("metadata"), Mapping):
                raise ImportPreviewError("Confirmed Preview chunk is invalid")
            text = chunk.get("text")
            metadata = chunk["metadata"]
            page = metadata.get("page")
            chunk_index = metadata.get("chunkIndex")
            if not isinstance(text, str) or not text.strip() or len(text) > 500:
                raise ImportPreviewError(
                    "Confirmed Preview chunk text must contain 1-500 characters"
                )
            if (
                isinstance(page, bool)
                or not isinstance(page, int)
                or page not in page_numbers
                or isinstance(chunk_index, bool)
                or not isinstance(chunk_index, int)
                or chunk_index < 1
            ):
                raise ImportPreviewError("Confirmed Preview chunk metadata is invalid")
            if (page, chunk_index) in keys:
                raise ImportPreviewError("Confirmed Preview chunk IDs must be unique")
            keys.add((page, chunk_index))
            section = metadata.get("section")
            if section is not None and not isinstance(section, str):
                raise ImportPreviewError("Confirmed Preview chunk section is invalid")

    def _extract(self, upload: ValidatedUpload) -> list[ExtractedPage]:
        with TemporaryDirectory(prefix="import-preview-") as directory:
            root = Path(directory)
            source = root / f"source{upload.extension}"
            source.write_bytes(upload.content)
            if upload.extension == ".pdf":
                return extract_pdf(source)
            if upload.extension == ".docx":
                return extract_docx(source)
            if upload.extension == ".doc":
                converted = convert_doc_to_docx(source, root / "converted")
                return extract_docx(converted)
        raise ImportPreviewError("Unsupported file type for preview")

    def _parse_collections(
        self,
        document_type: str,
        text: str,
        *,
        curriculum_id: ObjectId,
        curriculum: dict[str, Any],
        source_document_id: ObjectId,
    ) -> dict[str, list[dict[str, Any]]]:
        empty = {
            "curricula": [],
            "persons": [],
            "educations": [],
            "academic_works": [],
            "appointments": [],
        }
        if document_type == "curriculum":
            parsed = CurriculumData.model_validate(curriculum)
            seeds = parse_curriculum_people(text)
            curriculum_values = parsed.model_dump()
            empty["curricula"] = [
                self._with_source(
                    curriculum_values,
                    "curricula",
                    source_document_id,
                    source_fields={
                        "curriculumCode",
                        "curriculumName",
                        "curriculumYear",
                    },
                )
            ]
            empty["persons"] = [
                self._with_source(
                    seed.person.model_dump(exclude_none=True),
                    "persons",
                    source_document_id,
                )
                for seed in seeds
            ]
            empty["educations"] = [
                {
                    **self._with_source(
                        education.model_dump(),
                        "educations",
                        source_document_id,
                        extra_fields={"personId"},
                    ),
                    "_personIndex": person_index,
                }
                for person_index, seed in enumerate(seeds)
                for education in seed.educations
            ]
            return empty

        if document_type == "cv":
            parsed = parse_cv(text)
            empty["persons"] = [
                self._with_source(
                    parsed.person.model_dump(exclude_none=True),
                    "persons",
                    source_document_id,
                )
            ]
            empty["educations"] = [
                {
                    **self._with_source(
                        item.model_dump(),
                        "educations",
                        source_document_id,
                        extra_fields={"personId"},
                    ),
                    "_personIndex": 0,
                }
                for item in parsed.educations
            ]
            empty["academic_works"] = [
                {
                    **self._with_source(
                        item.model_dump(),
                        "academic_works",
                        source_document_id,
                        extra_fields={"personId"},
                    ),
                    "_personIndex": 0,
                }
                for item in parsed.academicWorks
            ]
            return empty

        if document_type == "appointment":
            items = parse_appointments(
                text,
                curriculum_code=curriculum["curriculumCode"],
            )
            empty["appointments"] = [
                {
                    "curriculumId": str(curriculum_id),
                    "personId": str(self._person_id(item.personReference.fullName)),
                    **item.appointment.model_dump(),
                    "sources": [
                        preview_source(
                            source_document_id,
                            "appointments",
                        )
                    ],
                }
                for item in items
            ]
            return empty

        raise ImportPreviewError("Unsupported documentType for preview")

    def _curriculum(self, value: str) -> tuple[ObjectId, dict[str, Any]]:
        try:
            object_id = ObjectId(value)
        except (InvalidId, TypeError) as exc:
            raise ImportPreviewError("curriculumId must be a valid ObjectId") from exc
        curriculum = self._database["curricula"].find_one({"_id": object_id})
        if curriculum is None:
            raise ImportPreviewError(
                "curriculumId must reference an existing curricula._id"
            )
        return object_id, curriculum

    def _person_id(self, full_name: str) -> ObjectId:
        person = self._database["persons"].find_one({"fullName": full_name})
        if person is not None:
            return person["_id"]
        normalized = normalize_person_name(full_name)
        matches = list(
            self._database["persons"].find(
                {
                    "firstName": normalized.firstName,
                    "lastName": normalized.lastName,
                },
                {"_id": 1},
            ).limit(2)
        )
        if not matches:
            raise ImportPreviewError(
                f"Appointment person reference was not found: {full_name}"
            )
        if len(matches) > 1:
            raise ImportPreviewError(
                f"Appointment person reference is ambiguous: {full_name}"
            )
        return matches[0]["_id"]

    @staticmethod
    def _usage_preview(
        collections: dict[str, list[dict[str, Any]]],
        *,
        curriculum_id: str,
    ) -> list[dict[str, Any]]:
        data_types = {
            "curricula": "curriculum",
            "persons": "person",
            "educations": "education",
            "academic_works": "academicWork",
            "appointments": "appointment",
        }
        return [
            {
                "dataType": data_types[collection],
                "dataId": "resolved after upsert",
                "curriculumId": curriculum_id,
                "psCodes": [],
                "roles": [],
                "templateFields": [],
                "_source": f"{collection}[{index}]",
            }
            for collection, items in collections.items()
            for index, _item in enumerate(items)
        ]

    @staticmethod
    def _without_link_and_sources(item: Any) -> dict[str, Any]:
        if not isinstance(item, Mapping):
            raise ImportPreviewError("Confirmed Preview record is invalid")
        return {
            key: value
            for key, value in item.items()
            if key not in {"_personIndex", "sources"}
        }

    @staticmethod
    def _without_sources(item: Any) -> dict[str, Any]:
        if not isinstance(item, Mapping):
            raise ImportPreviewError("Confirmed Preview record is invalid")
        return {key: value for key, value in item.items() if key != "sources"}

    @staticmethod
    def _validated_record_sources(
        item: Any,
        document_id: Any,
        collection_name: str,
        required_fields: Iterable[str],
    ) -> list[dict[str, Any]]:
        if not isinstance(item, Mapping):
            raise ImportPreviewError("Confirmed Preview record is invalid")
        return validate_sources(
            item.get("sources"),
            expected_document_id=document_id,
            collection_name=collection_name,
            required_fields=required_fields,
        )

    @staticmethod
    def _with_source(
        values: dict[str, Any],
        collection_name: str,
        document_id: ObjectId,
        *,
        extra_fields: set[str] | None = None,
        source_fields: set[str] | None = None,
    ) -> dict[str, Any]:
        fields = set(values)
        fields.update(extra_fields or set())
        return {
            **values,
            "sources": [
                preview_source(
                    document_id,
                    collection_name,
                    present_fields=source_fields or fields,
                )
            ],
        }

    @staticmethod
    def _validate_person_index(item: Any, person_count: int) -> None:
        if not isinstance(item, Mapping):
            raise ImportPreviewError("Confirmed Preview record is invalid")
        index = item.get("_personIndex")
        if (
            isinstance(index, bool)
            or not isinstance(index, int)
            or index < 0
            or index >= person_count
        ):
            raise ImportPreviewError(
                "Preview _personIndex does not reference a persons record"
            )
