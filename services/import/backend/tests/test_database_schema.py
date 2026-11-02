from app.database.schema import COLLECTION_SPECS


EXPECTED_FIELDS = {
    "curricula": {
        "_id",
        "curriculumCode",
        "curriculumName",
        "curriculumYear",
        "version",
        "status",
        "sources",
        "timestamp",
    },
    "persons": {
        "_id",
        "title",
        "firstName",
        "lastName",
        "fullName",
        "academicPosition",
        "hasTeachingExperience",
        "sources",
        "timestamp",
    },
    "educations": {
        "_id",
        "personId",
        "degree",
        "field",
        "institution",
        "graduationYear",
        "sources",
        "timestamp",
    },
    "appointments": {
        "_id",
        "curriculumId",
        "personId",
        "role",
        "roleName",
        "effectiveDate",
        "appointmentOrder",
        "status",
        "sources",
        "timestamp",
    },
    "academic_works": {
        "_id",
        "personId",
        "workType",
        "title",
        "publicationYear",
        "database",
        "quartile",
        "sources",
        "timestamp",
    },
    "documents": {
        "_id",
        "documentType",
        "fileType",
        "fileName",
        "curriculumId",
        "originalFile",
        "convertedFile",
        "extractedText",
        "status",
        "timestamp",
    },
    "ps_requirements": {
        "_id",
        "psCode",
        "requirement",
        "config",
        "active",
        "timestamp",
    },
    "data_usages": {
        "_id",
        "dataType",
        "dataId",
        "curriculumId",
        "psCodes",
        "roles",
        "templateFields",
        "timestamp",
    },
    "template_ps": {
        "_id",
        "version",
        "fileName",
        "fileType",
        "originalFile",
        "timestamp",
    },
}


def test_only_import_service_collections_are_bootstrapped() -> None:
    assert set(COLLECTION_SPECS) == set(EXPECTED_FIELDS)
    assert "generated_documents" not in COLLECTION_SPECS


def test_collection_validators_use_exact_srs_fields() -> None:
    for collection_name, expected_fields in EXPECTED_FIELDS.items():
        schema = COLLECTION_SPECS[collection_name].schema
        assert schema["additionalProperties"] is False
        expected_required = expected_fields
        if collection_name == "persons":
            expected_required = expected_fields - {"hasTeachingExperience"}
        assert set(schema["required"]) == expected_required
        assert set(schema["properties"]) == expected_fields


def test_persons_validator_forbids_role_fields() -> None:
    schema = COLLECTION_SPECS["persons"].schema
    properties = schema["properties"]
    assert "role" not in properties
    assert "roleName" not in properties
    assert properties["hasTeachingExperience"] == {"bsonType": "bool"}
    assert "hasTeachingExperience" not in schema["required"]


def test_template_validator_supports_only_docx_and_pdf() -> None:
    properties = COLLECTION_SPECS["template_ps"].schema["properties"]
    assert properties["fileType"] == {"enum": ["docx", "pdf"]}


def test_relationship_fields_require_object_ids() -> None:
    relationships = {
        "appointments": ("curriculumId", "personId"),
        "educations": ("personId",),
        "academic_works": ("personId",),
        "documents": ("curriculumId",),
        "data_usages": ("curriculumId", "dataId"),
    }
    for collection_name, fields in relationships.items():
        properties = COLLECTION_SPECS[collection_name].schema["properties"]
        for field in fields:
            assert properties[field] == {"bsonType": "objectId"}


def test_custom_indexes_do_not_invent_unique_constraints() -> None:
    for collection_name, spec in COLLECTION_SPECS.items():
        for index in spec.indexes:
            if collection_name == "template_ps":
                assert index.document.get("unique", False) is True
            else:
                assert index.document.get("unique", False) is False
