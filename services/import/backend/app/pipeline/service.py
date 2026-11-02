"""SRS processing steps 05-20 composed into one import pipeline."""

import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import ReturnDocument
from pymongo.database import Database

from app.chunking import Chunk, ChunkMetadata, DocumentChunker, PageContext
from app.config import Settings
from app.extraction.models import ExtractedPage
from app.extraction.service import DocumentExtractionService
from app.parsing import (
    parse_appointments,
    parse_curriculum,
    parse_curriculum_people,
    parse_cv,
)
from app.parsing.models import (
    AcademicWorkData,
    AppointmentData,
    CurriculumData,
    EducationData,
    PersonData,
)
from app.persistence import (
    DataUsageMapping,
    StructuredDataWriter,
    database_source,
    validate_sources,
)
from app.vectorization import BgeM3Embedder, ChromaVectorStore

logger = logging.getLogger(__name__)

_EMPTY_USAGE = DataUsageMapping(psCodes=[], roles=[], templateFields=[])
_STRUCTURED_COLLECTIONS = {
    "curriculum": "curricula",
    "person": "persons",
    "education": "educations",
    "academicWork": "academic_works",
    "appointment": "appointments",
    "dataUsage": "data_usages",
}


class ImportPipelineError(RuntimeError):
    """Raised when a document cannot complete the locked import pipeline."""


@dataclass(frozen=True)
class PipelineResult:
    documentId: str
    status: str
    structuredRecords: dict[str, tuple[str, ...]]
    chunkCount: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "documentId": self.documentId,
            "status": self.status,
            "structuredRecords": {
                key: list(values) for key, values in self.structuredRecords.items()
            },
            "chunkCount": self.chunkCount,
        }


class ImportPipeline:
    """Run extraction through final validation for one documents record."""

    def __init__(
        self,
        settings: Settings,
        database: Database[dict[str, Any]],
        *,
        extraction_service: DocumentExtractionService | None = None,
        structured_writer: StructuredDataWriter | None = None,
        chunker: DocumentChunker | None = None,
        embedder: BgeM3Embedder | None = None,
        vector_store: ChromaVectorStore | None = None,
        usage_mappings: Mapping[str, DataUsageMapping] | None = None,
    ) -> None:
        self._settings = settings
        self._database = database
        self._extraction = extraction_service or DocumentExtractionService(
            settings, database
        )
        self._writer = structured_writer or StructuredDataWriter(database)
        self._chunker = chunker or DocumentChunker(settings)
        self._embedder = embedder or BgeM3Embedder(settings)
        self._vectors = vector_store or ChromaVectorStore(settings)
        self._usage_mappings = dict(usage_mappings or {})

    def process(
        self,
        document_id: ObjectId | str,
        *,
        preview_data: Mapping[str, Any] | None = None,
    ) -> PipelineResult:
        object_id = self._as_object_id(document_id)
        document = self._database["documents"].find_one_and_update(
            {
                "_id": object_id,
                "status": {"$in": ["uploaded", "failed"]},
            },
            {"$set": {"status": "processing", "timestamp": self._now()}},
            return_document=ReturnDocument.AFTER,
        )
        if document is None:
            existing = self._database["documents"].find_one({"_id": object_id})
            if existing is None:
                raise ImportPipelineError("Document record was not found")
            raise ImportPipelineError(
                f"Document cannot be processed from status={existing['status']}"
            )

        document_id_text = str(object_id)
        logger.info("Import pipeline started documentId=%s", document_id_text)
        try:
            self._extraction.process_document(document_id_text)
            document = self._required_document(object_id)
            pages = self._load_extracted_pages(document)
            combined_text = "\n".join(page.text for page in pages)

            if preview_data is None:
                structured_ids, person_id = self._parse_and_write(
                    document,
                    combined_text,
                )
            else:
                structured_ids, person_id = self._write_edited_preview(
                    document,
                    preview_data,
                )
            usage_ids = self._write_data_usages(
                structured_ids,
                curriculum_id=document["curriculumId"],
            )
            structured_ids["dataUsage"] = usage_ids

            if preview_data is None:
                contexts = self._page_contexts(pages, person_id)
                chunks = self._chunker.chunk_document(
                    document_id=object_id,
                    curriculum_id=document["curriculumId"],
                    document_type=document["documentType"],
                    pages=pages,
                    page_contexts=contexts,
                )
            else:
                chunks = self._edited_chunks(
                    document,
                    pages,
                    preview_data,
                    person_id=person_id,
                )
            embedded = self._embedder.embed_chunks(chunks)
            stored_count = self._vectors.upsert_document(embedded)
            self._final_validate(
                document=document,
                structured_ids=structured_ids,
                expected_chunk_ids={chunk.id for chunk in chunks},
                stored_count=stored_count,
            )

            update = self._database["documents"].update_one(
                {"_id": object_id, "status": "processing"},
                {"$set": {"status": "processed", "timestamp": self._now()}},
            )
            if update.modified_count != 1:
                raise ImportPipelineError("Final document status update failed")
            result = PipelineResult(
                documentId=document_id_text,
                status="processed",
                structuredRecords={
                    key: tuple(str(value) for value in values)
                    for key, values in structured_ids.items()
                },
                chunkCount=len(chunks),
            )
            logger.info(
                "Import pipeline completed documentId=%s chunks=%s status=processed",
                document_id_text,
                len(chunks),
            )
            return result
        except Exception:
            try:
                self._vectors.delete_document(document_id_text)
            except Exception:
                logger.exception(
                    "Incomplete ChromaDB cleanup failed documentId=%s",
                    document_id_text,
                )
            self._database["documents"].update_one(
                {"_id": object_id},
                {"$set": {"status": "failed", "timestamp": self._now()}},
            )
            logger.exception("Import pipeline failed documentId=%s", document_id_text)
            raise

    def _parse_and_write(
        self,
        document: dict[str, Any],
        text: str,
    ) -> tuple[dict[str, list[ObjectId]], ObjectId | None]:
        document_type = document["documentType"]
        curriculum_id: ObjectId = document["curriculumId"]
        logger.info(
            "Parsing started documentId=%s documentType=%s",
            document["_id"],
            document_type,
        )
        if document_type == "curriculum":
            selected = self._database["curricula"].find_one(
                {"_id": curriculum_id}
            )
            if selected is None:
                raise ImportPipelineError("documents.curriculumId was not found")
            parsed = parse_curriculum(text, reference=selected)
            parsed_key = (
                parsed.curriculumCode,
                parsed.curriculumYear,
                parsed.version,
            )
            selected_key = (
                selected["curriculumCode"],
                selected["curriculumYear"],
                selected["version"],
            )
            if parsed_key != selected_key:
                raise ImportPipelineError(
                    "Parsed curriculum does not match documents.curriculumId"
                )
            written_id = self._writer.upsert_curriculum(
                parsed,
                sources=[database_source(document["_id"], "curricula")],
            )
            if written_id != curriculum_id:
                raise ImportPipelineError("Curriculum relationship validation failed")
            person_ids: list[ObjectId] = []
            education_ids: list[ObjectId] = []
            for seed in parse_curriculum_people(text):
                person_values = seed.person.model_dump(exclude_none=True)
                person_id = self._writer.upsert_person(
                    seed.person,
                    sources=[
                        database_source(
                            document["_id"],
                            "persons",
                            present_fields=person_values.keys(),
                        )
                    ],
                )
                person_ids.append(person_id)
                education_ids.extend(
                    self._writer.upsert_education(
                        person_id,
                        education,
                        sources=[database_source(document["_id"], "educations")],
                    )
                    for education in seed.educations
                )
            logger.info(
                "Curriculum people write completed curriculumId=%s persons=%s educations=%s",
                curriculum_id,
                len(set(person_ids)),
                len(set(education_ids)),
            )
            return {
                "curriculum": [written_id],
                "person": list(dict.fromkeys(person_ids)),
                "education": list(dict.fromkeys(education_ids)),
            }, None

        if document_type == "cv":
            parsed = parse_cv(text)
            result = self._writer.upsert_cv(
                parsed,
                curriculum_id,
                source_document_id=document["_id"],
            )
            return (
                {
                    "person": [result.personId],
                    "education": list(result.educationIds),
                    "academicWork": list(result.academicWorkIds),
                },
                result.personId,
            )

        if document_type == "appointment":
            selected = self._database["curricula"].find_one(
                {"_id": curriculum_id}
            )
            if selected is None:
                raise ImportPipelineError("documents.curriculumId was not found")
            parsed_items = parse_appointments(
                text,
                curriculum_code=selected["curriculumCode"],
            )
            appointment_ids: list[ObjectId] = []
            person_ids: list[ObjectId] = []
            for parsed in parsed_items:
                appointment_id = self._writer.upsert_appointment(
                    parsed,
                    curriculum_id,
                    source_document_id=document["_id"],
                )
                appointment = self._database["appointments"].find_one(
                    {"_id": appointment_id}
                )
                if appointment is None:
                    raise ImportPipelineError(
                        "Appointment final relationship was not found"
                    )
                appointment_ids.append(appointment_id)
                person_ids.append(appointment["personId"])
            unique_person_ids = list(dict.fromkeys(person_ids))
            context_person_id = (
                unique_person_ids[0] if len(unique_person_ids) == 1 else None
            )
            return {
                "appointment": list(dict.fromkeys(appointment_ids))
            }, context_person_id

        raise ImportPipelineError("Unsupported documents.documentType")

    def _write_edited_preview(
        self,
        document: dict[str, Any],
        preview_data: Mapping[str, Any],
    ) -> tuple[dict[str, list[ObjectId]], ObjectId | None]:
        collections = preview_data.get("collections")
        if not isinstance(collections, Mapping):
            raise ImportPipelineError("Confirmed Preview collections are required")
        expected_names = {
            "curricula",
            "persons",
            "educations",
            "academic_works",
            "appointments",
        }
        if set(collections) != expected_names:
            raise ImportPipelineError("Confirmed Preview collection names are invalid")
        if any(not isinstance(collections[name], list) for name in expected_names):
            raise ImportPipelineError("Confirmed Preview records must be arrays")

        document_type = document["documentType"]
        curriculum_id: ObjectId = document["curriculumId"]
        structured_ids: dict[str, list[ObjectId]]
        person_context: ObjectId | None = None

        if document_type == "curriculum":
            if len(collections["curricula"]) != 1:
                raise ImportPipelineError(
                    "Curriculum Preview must contain exactly one curricula record"
                )
            curriculum_raw = collections["curricula"][0]
            curriculum_sources = self._confirmed_sources(
                curriculum_raw,
                document["_id"],
                "curricula",
                {"curriculumCode", "curriculumName", "curriculumYear"},
            )
            curriculum = CurriculumData.model_validate(
                self._without_sources(curriculum_raw)
            )
            selected = self._database["curricula"].find_one({"_id": curriculum_id})
            if selected is not None and (
                curriculum.curriculumCode,
                curriculum.curriculumYear,
                curriculum.version,
            ) != (
                selected["curriculumCode"],
                selected["curriculumYear"],
                selected["version"],
            ):
                raise ImportPipelineError(
                    "Edited curriculum does not match documents.curriculumId"
                )
            written_curriculum = self._writer.upsert_curriculum(
                curriculum,
                sources=curriculum_sources,
                curriculum_id=curriculum_id,
            )
            if written_curriculum != curriculum_id:
                raise ImportPipelineError("Curriculum relationship validation failed")
            person_ids = []
            for raw in collections["persons"]:
                person_values = self._without_sources(raw)
                person_ids.append(
                    self._writer.upsert_person(
                        PersonData.model_validate(person_values),
                        sources=self._confirmed_sources(
                            raw,
                            document["_id"],
                            "persons",
                            person_values.keys(),
                        ),
                    )
                )
            education_ids = [
                self._writer.upsert_education(
                    self._preview_person_id(raw, person_ids),
                    EducationData.model_validate(self._without_preview_link(raw)),
                    sources=self._confirmed_sources(
                        raw,
                        document["_id"],
                        "educations",
                        {"personId", "degree", "field", "institution", "graduationYear"},
                    ),
                )
                for raw in collections["educations"]
            ]
            if collections["academic_works"] or collections["appointments"]:
                raise ImportPipelineError(
                    "Curriculum Preview contains unsupported collection records"
                )
            structured_ids = {
                "curriculum": [written_curriculum],
                "person": list(dict.fromkeys(person_ids)),
                "education": list(dict.fromkeys(education_ids)),
            }

        elif document_type == "cv":
            if len(collections["persons"]) != 1:
                raise ImportPipelineError(
                    "CV Preview must contain exactly one persons record"
                )
            if collections["curricula"] or collections["appointments"]:
                raise ImportPipelineError("CV Preview contains unsupported records")
            person_raw = collections["persons"][0]
            person_values = self._without_sources(person_raw)
            person_id = self._writer.upsert_person(
                PersonData.model_validate(person_values),
                sources=self._confirmed_sources(
                    person_raw,
                    document["_id"],
                    "persons",
                    person_values.keys(),
                ),
            )
            person_ids = [person_id]
            education_ids = [
                self._writer.upsert_education(
                    self._preview_person_id(raw, person_ids),
                    EducationData.model_validate(self._without_preview_link(raw)),
                    sources=self._confirmed_sources(
                        raw,
                        document["_id"],
                        "educations",
                        {"personId", "degree", "field", "institution", "graduationYear"},
                    ),
                )
                for raw in collections["educations"]
            ]
            academic_ids = [
                self._writer.upsert_academic_work(
                    self._preview_person_id(raw, person_ids),
                    AcademicWorkData.model_validate(self._without_preview_link(raw)),
                    sources=self._confirmed_sources(
                        raw,
                        document["_id"],
                        "academic_works",
                        {
                            "personId",
                            "workType",
                            "title",
                            "publicationYear",
                            "database",
                            "quartile",
                        },
                    ),
                )
                for raw in collections["academic_works"]
            ]
            structured_ids = {
                "person": [person_id],
                "education": list(dict.fromkeys(education_ids)),
                "academicWork": list(dict.fromkeys(academic_ids)),
            }
            person_context = person_id

        elif document_type == "appointment":
            if any(
                collections[name]
                for name in ("curricula", "persons", "educations", "academic_works")
            ):
                raise ImportPipelineError(
                    "Appointment Preview contains unsupported collection records"
                )
            if not collections["appointments"]:
                raise ImportPipelineError(
                    "Appointment Preview must contain at least one appointment"
                )
            appointment_ids: list[ObjectId] = []
            person_ids = []
            for raw in collections["appointments"]:
                if not isinstance(raw, Mapping):
                    raise ImportPipelineError("Appointment Preview record is invalid")
                try:
                    raw_curriculum_id = ObjectId(raw.get("curriculumId"))
                    person_id = ObjectId(raw.get("personId"))
                except (InvalidId, TypeError) as exc:
                    raise ImportPipelineError(
                        "Appointment Preview relationships must be ObjectIds"
                    ) from exc
                if raw_curriculum_id != curriculum_id:
                    raise ImportPipelineError(
                        "Appointment Preview curriculumId cannot be changed"
                    )
                values = {
                    key: value
                    for key, value in raw.items()
                    if key not in {"curriculumId", "personId", "sources"}
                }
                appointment_ids.append(
                    self._writer.upsert_appointment_for_person(
                        AppointmentData.model_validate(values),
                        curriculum_id,
                        person_id,
                        sources=self._confirmed_sources(
                            raw,
                            document["_id"],
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
                        ),
                    )
                )
                person_ids.append(person_id)
            unique_person_ids = list(dict.fromkeys(person_ids))
            person_context = unique_person_ids[0] if len(unique_person_ids) == 1 else None
            structured_ids = {
                "appointment": list(dict.fromkeys(appointment_ids))
            }
        else:
            raise ImportPipelineError("Unsupported documents.documentType")

        logger.info(
            "Confirmed Preview write completed documentId=%s documentType=%s",
            document["_id"],
            document_type,
        )
        return structured_ids, person_context

    def _edited_chunks(
        self,
        document: dict[str, Any],
        pages: list[ExtractedPage],
        preview_data: Mapping[str, Any],
        *,
        person_id: ObjectId | None,
    ) -> list[Chunk]:
        raw_chunks = preview_data.get("chunks")
        if not isinstance(raw_chunks, list) or not raw_chunks:
            raise ImportPipelineError("Confirmed Preview must contain at least one chunk")
        page_numbers = {page.pageNumber for page in pages}
        chunks: list[Chunk] = []
        keys: set[tuple[int, int]] = set()
        for raw in raw_chunks:
            if not isinstance(raw, Mapping) or not isinstance(raw.get("metadata"), Mapping):
                raise ImportPipelineError("Confirmed Preview chunk is invalid")
            text = raw.get("text")
            metadata = raw["metadata"]
            page = metadata.get("page")
            chunk_index = metadata.get("chunkIndex")
            if not isinstance(text, str) or not text.strip() or len(text) > 500:
                raise ImportPipelineError(
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
                raise ImportPipelineError("Confirmed Preview chunk metadata is invalid")
            key = (page, chunk_index)
            if key in keys:
                raise ImportPipelineError("Confirmed Preview chunk IDs must be unique")
            keys.add(key)
            section = metadata.get("section")
            if section is not None and not isinstance(section, str):
                raise ImportPipelineError("Confirmed Preview chunk section is invalid")
            chunk_metadata = ChunkMetadata(
                documentId=str(document["_id"]),
                curriculumId=str(document["curriculumId"]),
                documentType=document["documentType"],
                page=page,
                chunkIndex=chunk_index,
                section=section.strip() if section and section.strip() else None,
                personId=str(person_id) if person_id is not None else None,
            )
            chunks.append(
                Chunk(
                    id=f"{document['_id']}-p{page}-c{chunk_index:02d}",
                    text=text,
                    metadata=chunk_metadata,
                )
            )
        return chunks

    @staticmethod
    def _without_preview_link(raw: Any) -> dict[str, Any]:
        if not isinstance(raw, Mapping):
            raise ImportPipelineError("Confirmed Preview record is invalid")
        return {
            key: value
            for key, value in raw.items()
            if key not in {"_personIndex", "sources"}
        }

    @staticmethod
    def _without_sources(raw: Any) -> dict[str, Any]:
        if not isinstance(raw, Mapping):
            raise ImportPipelineError("Confirmed Preview record is invalid")
        return {key: value for key, value in raw.items() if key != "sources"}

    @staticmethod
    def _confirmed_sources(
        raw: Any,
        document_id: ObjectId,
        collection_name: str,
        required_fields: Any,
    ) -> list[dict[str, Any]]:
        if not isinstance(raw, Mapping):
            raise ImportPipelineError("Confirmed Preview record is invalid")
        return validate_sources(
            raw.get("sources"),
            expected_document_id=document_id,
            collection_name=collection_name,
            required_fields=required_fields,
        )

    @staticmethod
    def _preview_person_id(raw: Any, person_ids: list[ObjectId]) -> ObjectId:
        if not isinstance(raw, Mapping):
            raise ImportPipelineError("Confirmed Preview record is invalid")
        index = raw.get("_personIndex")
        if isinstance(index, bool) or not isinstance(index, int) or index < 0:
            raise ImportPipelineError("Preview _personIndex must be an integer")
        try:
            return person_ids[index]
        except IndexError as exc:
            raise ImportPipelineError(
                "Preview _personIndex does not reference a persons record"
            ) from exc

    def _write_data_usages(
        self,
        structured_ids: Mapping[str, list[ObjectId]],
        *,
        curriculum_id: ObjectId,
    ) -> list[ObjectId]:
        usage_ids: list[ObjectId] = []
        for data_type, record_ids in structured_ids.items():
            mapping = self._usage_mappings.get(data_type, _EMPTY_USAGE)
            for record_id in record_ids:
                usage_ids.append(
                    self._writer.upsert_data_usage(
                        data_type=data_type,
                        data_id=record_id,
                        curriculum_id=curriculum_id,
                        mapping=mapping,
                    )
                )
        return usage_ids

    def _load_extracted_pages(self, document: dict[str, Any]) -> list[ExtractedPage]:
        relative_path = PurePosixPath(document["extractedText"]["path"])
        expected_prefix = (
            "project-data",
            "documents",
            "extracted",
            document["documentType"],
        )
        if relative_path.is_absolute() or relative_path.parts[:4] != expected_prefix:
            raise ImportPipelineError("Extracted text path is invalid")
        root = self._settings.project_data_root.resolve()
        file_path = root.joinpath(*relative_path.parts[1:]).resolve()
        if not file_path.is_relative_to(root) or not file_path.is_file():
            raise ImportPipelineError("Extracted text file was not found")

        try:
            payload = json.loads(file_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ImportPipelineError("Extracted text file is invalid") from exc
        if (
            payload.get("documentId") != str(document["_id"])
            or payload.get("documentType") != document["documentType"]
            or not isinstance(payload.get("pages"), list)
        ):
            raise ImportPipelineError("Extracted text identity validation failed")

        pages: list[ExtractedPage] = []
        for raw_page in payload["pages"]:
            if (
                not isinstance(raw_page, dict)
                or isinstance(raw_page.get("pageNumber"), bool)
                or not isinstance(raw_page.get("pageNumber"), int)
                or not isinstance(raw_page.get("text"), str)
            ):
                raise ImportPipelineError("Extracted page is invalid")
            pages.append(
                ExtractedPage(
                    pageNumber=raw_page["pageNumber"],
                    text=raw_page["text"],
                )
            )
        if not pages:
            raise ImportPipelineError("Extracted document contains no pages")
        return pages

    def _final_validate(
        self,
        *,
        document: dict[str, Any],
        structured_ids: Mapping[str, list[ObjectId]],
        expected_chunk_ids: set[str],
        stored_count: int,
    ) -> None:
        if self._database["curricula"].find_one(
            {"_id": document["curriculumId"]}, {"_id": 1}
        ) is None:
            raise ImportPipelineError(
                "Final documents.curriculumId relationship validation failed"
            )
        for data_type, record_ids in structured_ids.items():
            collection_name = _STRUCTURED_COLLECTIONS[data_type]
            records = list(
                self._database[collection_name].find(
                    {"_id": {"$in": record_ids}}
                )
            )
            if len(records) != len(set(record_ids)):
                raise ImportPipelineError(
                    f"Final MongoDB validation failed: {collection_name}"
                )
            if collection_name in {
                "curricula",
                "persons",
                "educations",
                "academic_works",
                "appointments",
            }:
                for record in records:
                    sources = record.get("sources")
                    if not isinstance(sources, list) or not sources:
                        raise ImportPipelineError(
                            f"Final Source validation failed: {collection_name}"
                        )
                    source_ids = [source.get("documentId") for source in sources]
                    if self._database["documents"].count_documents(
                        {"_id": {"$in": source_ids}}
                    ) != len(set(source_ids)):
                        raise ImportPipelineError(
                            f"Final Source relationship failed: {collection_name}"
                        )
        if stored_count != len(expected_chunk_ids):
            raise ImportPipelineError("Final ChromaDB count validation failed")
        actual_chunk_ids = self._vectors.get_document_ids(str(document["_id"]))
        if actual_chunk_ids != expected_chunk_ids:
            raise ImportPipelineError("Final ChromaDB ID validation failed")

        original_path = PurePosixPath(document["originalFile"]["path"])
        expected_prefix = (
            "project-data",
            "documents",
            "original",
            document["documentType"],
        )
        if original_path.is_absolute() or original_path.parts[:4] != expected_prefix:
            raise ImportPipelineError("Final original-file traceability failed")
        root = self._settings.project_data_root.resolve()
        original_file = root.joinpath(*original_path.parts[1:]).resolve()
        if not original_file.is_relative_to(root) or not original_file.is_file():
            raise ImportPipelineError("Final original-file traceability failed")

    def _required_document(self, document_id: ObjectId) -> dict[str, Any]:
        document = self._database["documents"].find_one({"_id": document_id})
        if document is None:
            raise ImportPipelineError("Document record was not found")
        return document

    @staticmethod
    def _page_contexts(
        pages: list[ExtractedPage],
        person_id: ObjectId | None,
    ) -> dict[int, PageContext]:
        if person_id is None:
            return {}
        return {
            page.pageNumber: PageContext(personId=str(person_id)) for page in pages
        }

    @staticmethod
    def _as_object_id(value: ObjectId | str) -> ObjectId:
        if isinstance(value, ObjectId):
            return value
        try:
            return ObjectId(value)
        except (InvalidId, TypeError) as exc:
            raise ImportPipelineError("documentId must be a valid ObjectId") from exc

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)
