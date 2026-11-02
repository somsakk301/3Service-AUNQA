"""Locked MongoDB collection validators and non-unique query indexes."""

from dataclasses import dataclass
from typing import Any

from pymongo import ASCENDING, IndexModel


def _object_id() -> dict[str, Any]:
    return {"bsonType": "objectId"}


def _string() -> dict[str, Any]:
    return {"bsonType": "string"}


def _integer() -> dict[str, Any]:
    return {"bsonType": ["int", "long"]}


def _timestamp() -> dict[str, Any]:
    return {"bsonType": "date"}


def _local_file_reference() -> dict[str, Any]:
    return {
        "bsonType": "object",
        "additionalProperties": False,
        "required": ["storage", "path"],
        "properties": {
            "storage": {"enum": ["local"]},
            "path": _string(),
        },
    }


def _sources() -> dict[str, Any]:
    return {
        "bsonType": "array",
        "items": {
            "bsonType": "object",
            "additionalProperties": False,
            "required": ["documentId", "pageNumbers", "fieldPaths"],
            "properties": {
                "documentId": _object_id(),
                "pageNumbers": {"bsonType": "array", "items": _integer()},
                "fieldPaths": {"bsonType": "array", "items": _string()},
            },
        },
    }


def _collection_schema(
    properties: dict[str, Any],
    *,
    optional_fields: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    return {
        "bsonType": "object",
        "additionalProperties": False,
        "required": [
            field_name
            for field_name in properties
            if field_name not in optional_fields
        ],
        "properties": properties,
    }


@dataclass(frozen=True)
class CollectionSpec:
    schema: dict[str, Any]
    indexes: tuple[IndexModel, ...]


COLLECTION_SPECS: dict[str, CollectionSpec] = {
    "curricula": CollectionSpec(
        schema=_collection_schema(
            {
                "_id": _object_id(),
                "curriculumCode": _string(),
                "curriculumName": _string(),
                "curriculumYear": _integer(),
                "version": _integer(),
                "status": _string(),
                "sources": _sources(),
                "timestamp": _timestamp(),
            }
        ),
        indexes=(
            IndexModel(
                [
                    ("curriculumCode", ASCENDING),
                    ("curriculumYear", ASCENDING),
                    ("version", ASCENDING),
                ],
                name="idx_curricula_code_year_version",
            ),
        ),
    ),
    "persons": CollectionSpec(
        schema=_collection_schema(
            {
                "_id": _object_id(),
                "title": _string(),
                "firstName": _string(),
                "lastName": _string(),
                "fullName": _string(),
                "academicPosition": _string(),
                "hasTeachingExperience": {"bsonType": "bool"},
                "sources": _sources(),
                "timestamp": _timestamp(),
            },
            optional_fields=frozenset({"hasTeachingExperience"}),
        ),
        indexes=(
            IndexModel([("fullName", ASCENDING)], name="idx_persons_full_name"),
        ),
    ),
    "educations": CollectionSpec(
        schema=_collection_schema(
            {
                "_id": _object_id(),
                "personId": _object_id(),
                "degree": _string(),
                "field": _string(),
                "institution": _string(),
                "graduationYear": _integer(),
                "sources": _sources(),
                "timestamp": _timestamp(),
            }
        ),
        indexes=(
            IndexModel([("personId", ASCENDING)], name="idx_educations_person_id"),
        ),
    ),
    "appointments": CollectionSpec(
        schema=_collection_schema(
            {
                "_id": _object_id(),
                "curriculumId": _object_id(),
                "personId": _object_id(),
                "role": {"enum": ["programmeResponsible", "programmeStaff"]},
                "roleName": _string(),
                "effectiveDate": {"bsonType": ["date", "string"]},
                "appointmentOrder": {
                    "bsonType": "object",
                    "additionalProperties": False,
                    "required": ["orderNumber", "orderDate"],
                    "properties": {
                        "orderNumber": _string(),
                        "orderDate": {"bsonType": ["date", "string"]},
                    },
                },
                "status": _string(),
                "sources": _sources(),
                "timestamp": _timestamp(),
            }
        ),
        indexes=(
            IndexModel(
                [("curriculumId", ASCENDING), ("personId", ASCENDING)],
                name="idx_appointments_curriculum_person",
            ),
            IndexModel([("role", ASCENDING)], name="idx_appointments_role"),
        ),
    ),
    "academic_works": CollectionSpec(
        schema=_collection_schema(
            {
                "_id": _object_id(),
                "personId": _object_id(),
                "workType": _string(),
                "title": _string(),
                "publicationYear": _integer(),
                "database": _string(),
                "quartile": _string(),
                "sources": _sources(),
                "timestamp": _timestamp(),
            }
        ),
        indexes=(
            IndexModel(
                [("personId", ASCENDING)], name="idx_academic_works_person_id"
            ),
            IndexModel(
                [("publicationYear", ASCENDING)],
                name="idx_academic_works_publication_year",
            ),
        ),
    ),
    "documents": CollectionSpec(
        schema=_collection_schema(
            {
                "_id": _object_id(),
                "documentType": {"enum": ["curriculum", "cv", "appointment"]},
                "fileType": {"enum": ["pdf", "doc", "docx"]},
                "fileName": _string(),
                "curriculumId": _object_id(),
                "originalFile": _local_file_reference(),
                "convertedFile": _local_file_reference(),
                "extractedText": _local_file_reference(),
                "status": {
                    "enum": ["uploaded", "processing", "processed", "failed"]
                },
                "timestamp": _timestamp(),
            }
        ),
        indexes=(
            IndexModel(
                [("curriculumId", ASCENDING), ("documentType", ASCENDING)],
                name="idx_documents_curriculum_type",
            ),
            IndexModel([("status", ASCENDING)], name="idx_documents_status"),
        ),
    ),
    "ps_requirements": CollectionSpec(
        schema=_collection_schema(
            {
                "_id": _object_id(),
                "psCode": _string(),
                "requirement": _string(),
                "config": {"bsonType": "object"},
                "active": {"bsonType": "bool"},
                "timestamp": _timestamp(),
            }
        ),
        indexes=(
            IndexModel([("psCode", ASCENDING)], name="idx_ps_requirements_code"),
        ),
    ),
    "data_usages": CollectionSpec(
        schema=_collection_schema(
            {
                "_id": _object_id(),
                "dataType": _string(),
                "dataId": _object_id(),
                "curriculumId": _object_id(),
                "psCodes": {"bsonType": "array", "items": _string()},
                "roles": {"bsonType": "array", "items": _string()},
                "templateFields": {"bsonType": "array", "items": _string()},
                "timestamp": _timestamp(),
            }
        ),
        indexes=(
            IndexModel(
                [("curriculumId", ASCENDING)],
                name="idx_data_usages_curriculum_id",
            ),
            IndexModel(
                [("dataType", ASCENDING), ("dataId", ASCENDING)],
                name="idx_data_usages_type_data_id",
            ),
        ),
    ),
    "template_ps": CollectionSpec(
        schema=_collection_schema(
            {
                "_id": _object_id(),
                "version": _integer(),
                "fileName": _string(),
                "fileType": {"enum": ["docx", "pdf"]},
                "originalFile": _local_file_reference(),
                "timestamp": _timestamp(),
            }
        ),
        indexes=(
            IndexModel(
                [("version", ASCENDING)],
                name="idx_template_ps_version",
                unique=True,
            ),
        ),
    ),
}
