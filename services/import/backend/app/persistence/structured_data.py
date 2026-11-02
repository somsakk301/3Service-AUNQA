"""Phase 6 deduplicating MongoDB writes and ObjectId relationships."""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from pydantic import BaseModel, ConfigDict
from pymongo import ReturnDocument
from pymongo.database import Database

from app.parsing.models import (
    AcademicWorkData,
    AppointmentData,
    AppointmentParseResult,
    CurriculumData,
    CVParseResult,
    EducationData,
    PersonData,
)
from app.parsing.normalization import normalize_person_name
from app.persistence.provenance import database_source

logger = logging.getLogger(__name__)

_DATA_TYPE_COLLECTIONS = {
    "curriculum": "curricula",
    "person": "persons",
    "education": "educations",
    "appointment": "appointments",
    "academicWork": "academic_works",
}
_PS_CODES = {f"PS-{number:02d}" for number in range(1, 10)}


class StructuredDataError(ValueError):
    """Raised when an SRS relationship or mapping cannot be validated."""


class DataUsageMapping(BaseModel):
    """Caller-supplied mapping because the SRS does not define mapping values."""

    model_config = ConfigDict(extra="forbid")

    psCodes: list[str]
    roles: list[str]
    templateFields: list[str]


@dataclass(frozen=True)
class CVWriteResult:
    personId: ObjectId
    educationIds: tuple[ObjectId, ...]
    academicWorkIds: tuple[ObjectId, ...]


class StructuredDataWriter:
    """Write normalized records without changing the locked MongoDB schema."""

    def __init__(self, database: Database[dict[str, Any]]) -> None:
        self._database = database

    def upsert_curriculum(
        self,
        data: CurriculumData,
        *,
        sources: list[dict[str, Any]] | None = None,
        curriculum_id: ObjectId | str | None = None,
    ) -> ObjectId:
        values = {**data.model_dump(), "sources": sources or []}
        natural_key = {
            "curriculumCode": data.curriculumCode,
            "curriculumYear": data.curriculumYear,
            "version": data.version,
        }
        if curriculum_id is not None:
            desired_id = self._as_object_id(curriculum_id, "curriculumId")
            existing_key = self._database["curricula"].find_one(natural_key, {"_id": 1})
            if existing_key is not None and existing_key["_id"] != desired_id:
                raise StructuredDataError(
                    "Curriculum natural key already belongs to another ObjectId"
                )
            existing_id = self._database["curricula"].find_one(
                {"_id": desired_id},
                {"curriculumCode": 1, "curriculumYear": 1, "version": 1},
            )
            if existing_id is not None and any(
                existing_id.get(field) != value
                for field, value in natural_key.items()
            ):
                raise StructuredDataError(
                    "curriculumId already belongs to another curriculum"
                )
            natural_key = {"_id": desired_id}
        result = self._upsert(
            "curricula",
            natural_key,
            values,
        )
        return result["_id"]

    def upsert_cv(
        self,
        data: CVParseResult,
        curriculum_id: ObjectId | str,
        source_document_id: ObjectId | str | None = None,
    ) -> CVWriteResult:
        curriculum_object_id = self._as_object_id(curriculum_id, "curriculumId")
        self._require_exists("curricula", curriculum_object_id, "curriculumId")

        person_values = data.person.model_dump(exclude_none=True)
        person_sources = (
            [
                database_source(
                    source_document_id,
                    "persons",
                    present_fields=person_values.keys(),
                )
            ]
            if source_document_id is not None
            else []
        )
        person_id = self.upsert_person(data.person, sources=person_sources)
        education_ids = tuple(
            self.upsert_education(
                person_id,
                education,
                sources=(
                    [database_source(source_document_id, "educations")]
                    if source_document_id is not None
                    else []
                ),
            )
            for education in data.educations
        )
        academic_work_ids = tuple(
            self.upsert_academic_work(
                person_id,
                work,
                sources=(
                    [database_source(source_document_id, "academic_works")]
                    if source_document_id is not None
                    else []
                ),
            )
            for work in data.academicWorks
        )
        logger.info(
            "MongoDB CV write completed curriculumId=%s personId=%s educations=%s academicWorks=%s",
            curriculum_object_id,
            person_id,
            len(education_ids),
            len(academic_work_ids),
        )
        return CVWriteResult(
            personId=person_id,
            educationIds=education_ids,
            academicWorkIds=academic_work_ids,
        )

    def upsert_person(
        self,
        data: PersonData,
        *,
        sources: list[dict[str, Any]] | None = None,
    ) -> ObjectId:
        matches = list(
            self._database["persons"].find(
                {"firstName": data.firstName, "lastName": data.lastName}
            ).limit(2)
        )
        if len(matches) > 1:
            raise StructuredDataError(
                "Person identity is ambiguous for normalized firstName and lastName"
            )

        values = {**data.model_dump(exclude_none=True), "sources": sources or []}
        if matches:
            existing = matches[0]
            # Curriculum documents may include an academic position while the
            # matching CV omits it. Keep the richer normalized identity while
            # still accepting CV-only fields such as hasTeachingExperience.
            if existing.get("academicPosition") and not data.academicPosition:
                values["academicPosition"] = existing["academicPosition"]
                values["fullName"] = existing["fullName"]
            if existing.get("title") and not data.title:
                values["title"] = existing["title"]
            result = self._upsert(
                "persons",
                {"_id": existing["_id"]},
                values,
            )
            return result["_id"]

        result = self._upsert(
            "persons",
            {"firstName": data.firstName, "lastName": data.lastName},
            values,
        )
        return result["_id"]

    def upsert_education(
        self,
        person_id: ObjectId | str,
        data: EducationData,
        *,
        sources: list[dict[str, Any]] | None = None,
    ) -> ObjectId:
        person_object_id = self._as_object_id(person_id, "personId")
        self._require_exists("persons", person_object_id, "personId")
        natural_key = {
            "personId": person_object_id,
            **data.model_dump(),
        }
        values = {
            **natural_key,
            "sources": sources or [],
        }
        result = self._upsert("educations", natural_key, values)
        return result["_id"]

    def upsert_academic_work(
        self,
        person_id: ObjectId | str,
        data: AcademicWorkData,
        *,
        sources: list[dict[str, Any]] | None = None,
    ) -> ObjectId:
        person_object_id = self._as_object_id(person_id, "personId")
        self._require_exists("persons", person_object_id, "personId")
        natural_key = {
            "personId": person_object_id,
            **data.model_dump(),
        }
        values = {
            **natural_key,
            "sources": sources or [],
        }
        result = self._upsert("academic_works", natural_key, values)
        return result["_id"]

    def upsert_appointment(
        self,
        data: AppointmentParseResult,
        curriculum_id: ObjectId | str,
        source_document_id: ObjectId | str | None = None,
    ) -> ObjectId:
        curriculum_object_id = self._as_object_id(curriculum_id, "curriculumId")
        curriculum = self._require_exists(
            "curricula", curriculum_object_id, "curriculumId"
        )
        if curriculum["curriculumCode"] != data.curriculumReference.curriculumCode:
            raise StructuredDataError(
                "Appointment curriculum reference does not match curriculumId"
            )

        person = self._database["persons"].find_one(
            {"fullName": data.personReference.fullName}
        )
        if person is None:
            normalized_reference = normalize_person_name(
                data.personReference.fullName
            )
            matches = list(
                self._database["persons"].find(
                    {
                        "firstName": normalized_reference.firstName,
                        "lastName": normalized_reference.lastName,
                    }
                ).limit(2)
            )
            if len(matches) > 1:
                raise StructuredDataError(
                    "Appointment person reference is ambiguous"
                )
            person = matches[0] if matches else None
        if person is None:
            raise StructuredDataError("Appointment person reference was not found")

        return self._upsert_appointment_record(
            data.appointment,
            curriculum_object_id,
            person["_id"],
            sources=(
                [database_source(source_document_id, "appointments")]
                if source_document_id is not None
                else []
            ),
        )

    def upsert_appointment_for_person(
        self,
        data: AppointmentData,
        curriculum_id: ObjectId | str,
        person_id: ObjectId | str,
        *,
        sources: list[dict[str, Any]] | None = None,
    ) -> ObjectId:
        """Write a confirmed Preview appointment using validated ObjectId links."""

        curriculum_object_id = self._as_object_id(curriculum_id, "curriculumId")
        person_object_id = self._as_object_id(person_id, "personId")
        return self._upsert_appointment_record(
            data,
            curriculum_object_id,
            person_object_id,
            sources=sources or [],
        )

    def upsert_data_usage(
        self,
        *,
        data_type: str,
        data_id: ObjectId | str,
        curriculum_id: ObjectId | str,
        mapping: DataUsageMapping,
    ) -> ObjectId:
        collection_name = _DATA_TYPE_COLLECTIONS.get(data_type)
        if collection_name is None:
            raise StructuredDataError("Unsupported dataType for data_usages")

        data_object_id = self._as_object_id(data_id, "dataId")
        curriculum_object_id = self._as_object_id(curriculum_id, "curriculumId")
        invalid_ps_codes = set(mapping.psCodes) - _PS_CODES
        if invalid_ps_codes:
            raise StructuredDataError("psCodes must be within PS-01 through PS-09")

        self._require_exists(collection_name, data_object_id, "dataId")
        self._require_exists("curricula", curriculum_object_id, "curriculumId")

        values = {
            "dataType": data_type,
            "dataId": data_object_id,
            "curriculumId": curriculum_object_id,
            "psCodes": self._unique(mapping.psCodes),
            "roles": self._unique(mapping.roles),
            "templateFields": self._unique(mapping.templateFields),
        }
        result = self._upsert(
            "data_usages",
            {
                "dataType": data_type,
                "dataId": data_object_id,
                "curriculumId": curriculum_object_id,
            },
            values,
        )
        return result["_id"]

    def _upsert_appointment_record(
        self,
        data: AppointmentData,
        curriculum_id: ObjectId,
        person_id: ObjectId,
        *,
        sources: list[dict[str, Any]],
    ) -> ObjectId:
        self._require_exists("curricula", curriculum_id, "curriculumId")
        self._require_exists("persons", person_id, "personId")
        values = {
            "curriculumId": curriculum_id,
            "personId": person_id,
            **data.model_dump(),
            "sources": sources,
        }
        result = self._upsert(
            "appointments",
            {
                "curriculumId": curriculum_id,
                "personId": person_id,
                "role": data.role,
                "appointmentOrder.orderNumber": data.appointmentOrder.orderNumber,
            },
            values,
        )
        return result["_id"]

    def _upsert(
        self,
        collection_name: str,
        natural_key: dict[str, Any],
        values: dict[str, Any],
    ) -> dict[str, Any]:
        if "sources" in values:
            existing = self._database[collection_name].find_one(
                natural_key,
                {"sources": 1},
            )
            values = {
                **values,
                "sources": self._merge_sources(
                    existing.get("sources", []) if existing else [],
                    values["sources"],
                ),
            }
        timestamp = datetime.now(timezone.utc)
        document = self._database[collection_name].find_one_and_update(
            natural_key,
            {"$set": {**values, "timestamp": timestamp}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        if document is None:
            raise StructuredDataError(f"MongoDB upsert failed: {collection_name}")
        logger.info(
            "MongoDB write collection=%s recordId=%s",
            collection_name,
            document["_id"],
        )
        return document

    def _require_exists(
        self,
        collection_name: str,
        object_id: ObjectId,
        field_name: str,
    ) -> dict[str, Any]:
        document = self._database[collection_name].find_one({"_id": object_id})
        if document is None:
            raise StructuredDataError(
                f"{field_name} does not reference an existing {collection_name} record"
            )
        return document

    @staticmethod
    def _as_object_id(value: ObjectId | str, field_name: str) -> ObjectId:
        if isinstance(value, ObjectId):
            return value
        try:
            return ObjectId(value)
        except (InvalidId, TypeError) as exc:
            raise StructuredDataError(f"{field_name} must be a valid ObjectId") from exc

    @staticmethod
    def _unique(values: list[str]) -> list[str]:
        return list(dict.fromkeys(values))

    @staticmethod
    def _merge_sources(
        existing: list[dict[str, Any]],
        incoming: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        merged: dict[ObjectId, dict[str, Any]] = {}
        for source in [*existing, *incoming]:
            document_id = source["documentId"]
            current = merged.setdefault(
                document_id,
                {
                    "documentId": document_id,
                    "pageNumbers": [],
                    "fieldPaths": [],
                },
            )
            current["pageNumbers"] = list(
                dict.fromkeys([*current["pageNumbers"], *source["pageNumbers"]])
            )
            current["fieldPaths"] = list(
                dict.fromkeys([*current["fieldPaths"], *source["fieldPaths"]])
            )
        return list(merged.values())
