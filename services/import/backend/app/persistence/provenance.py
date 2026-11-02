"""Verified document provenance for Monitor-facing structured records."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId


class ProvenanceError(ValueError):
    """Raised when a SourceReference is missing, fabricated, or incomplete."""


SOURCE_FIELDS: dict[str, frozenset[str]] = {
    "curricula": frozenset(
        {"curriculumCode", "curriculumName", "curriculumYear", "version", "status"}
    ),
    "persons": frozenset(
        {
            "title",
            "firstName",
            "lastName",
            "fullName",
            "academicPosition",
            "hasTeachingExperience",
        }
    ),
    "educations": frozenset(
        {"personId", "degree", "field", "institution", "graduationYear"}
    ),
    "academic_works": frozenset(
        {
            "personId",
            "workType",
            "title",
            "publicationYear",
            "database",
            "quartile",
        }
    ),
    "appointments": frozenset(
        {
            "curriculumId",
            "personId",
            "role",
            "roleName",
            "effectiveDate",
            "appointmentOrder.orderNumber",
            "appointmentOrder.orderDate",
            "status",
        }
    ),
}


def preview_source(
    document_id: ObjectId | str,
    collection_name: str,
    *,
    present_fields: Iterable[str] | None = None,
    page_numbers: Iterable[int] = (),
) -> dict[str, Any]:
    """Build one JSON-safe source from a real pending document identity."""

    object_id = _object_id(document_id)
    allowed = SOURCE_FIELDS[collection_name]
    fields = sorted(set(present_fields) if present_fields is not None else allowed)
    invalid = set(fields) - allowed
    if invalid:
        raise ProvenanceError(f"Unsupported source fieldPaths: {sorted(invalid)}")
    return {
        "documentId": str(object_id),
        "pageNumbers": _pages(page_numbers),
        "fieldPaths": fields,
    }


def database_source(
    document_id: ObjectId | str,
    collection_name: str,
    *,
    present_fields: Iterable[str] | None = None,
    page_numbers: Iterable[int] = (),
) -> dict[str, Any]:
    """Build the BSON representation stored in a structured record."""

    source = preview_source(
        document_id,
        collection_name,
        present_fields=present_fields,
        page_numbers=page_numbers,
    )
    source["documentId"] = _object_id(source["documentId"])
    return source


def validate_sources(
    raw_sources: Any,
    *,
    expected_document_id: ObjectId | str,
    collection_name: str,
    required_fields: Iterable[str],
) -> list[dict[str, Any]]:
    """Validate Preview sources and convert documentId strings to ObjectIds."""

    expected = _object_id(expected_document_id)
    allowed = SOURCE_FIELDS[collection_name]
    required = set(required_fields)
    if required - allowed:
        raise ProvenanceError("Required source fields are not valid for collection")
    if not isinstance(raw_sources, list) or not raw_sources:
        raise ProvenanceError(
            f"{collection_name} record must contain at least one verified source"
        )

    result: list[dict[str, Any]] = []
    covered: set[str] = set()
    for raw in raw_sources:
        if not isinstance(raw, Mapping) or set(raw) != {
            "documentId",
            "pageNumbers",
            "fieldPaths",
        }:
            raise ProvenanceError("SourceReference fields are invalid")
        document_id = _object_id(raw["documentId"])
        if document_id != expected:
            raise ProvenanceError(
                "SourceReference documentId must match the confirmed document"
            )
        pages = _pages(raw["pageNumbers"])
        fields = raw["fieldPaths"]
        if (
            not isinstance(fields, list)
            or not fields
            or any(not isinstance(field, str) or not field for field in fields)
        ):
            raise ProvenanceError("SourceReference fieldPaths must be non-empty strings")
        unique_fields = list(dict.fromkeys(fields))
        invalid = set(unique_fields) - allowed
        if invalid:
            raise ProvenanceError(f"Unsupported source fieldPaths: {sorted(invalid)}")
        covered.update(unique_fields)
        result.append(
            {
                "documentId": document_id,
                "pageNumbers": pages,
                "fieldPaths": unique_fields,
            }
        )
    missing = required - covered
    if missing:
        raise ProvenanceError(f"SourceReference does not cover fields: {sorted(missing)}")
    return result


def _object_id(value: ObjectId | str) -> ObjectId:
    if isinstance(value, ObjectId):
        return value
    try:
        return ObjectId(value)
    except (InvalidId, TypeError) as exc:
        raise ProvenanceError("SourceReference documentId must be a valid ObjectId") from exc


def _pages(values: Any) -> list[int]:
    if not isinstance(values, Iterable) or isinstance(values, (str, bytes, Mapping)):
        raise ProvenanceError("SourceReference pageNumbers must be an array")
    pages = list(values)
    if any(isinstance(page, bool) or not isinstance(page, int) or page < 1 for page in pages):
        raise ProvenanceError("SourceReference pageNumbers must contain positive integers")
    return list(dict.fromkeys(pages))
