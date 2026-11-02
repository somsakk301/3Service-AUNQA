"""Source-schema facts taken from the authoritative Data Dictionary / Data Schema.

Only what those documents state explicitly appears here: the collections, their fields (with
the documented type) and the relationships to `curricula`. These are not PS business rules;
every PS rule value comes from `ps_requirements`. `ps_requirements` itself is configuration,
not source data, and is deliberately absent.
"""
CURRICULUM_KEY = "_id"  # curricula._id (PK)
MONITORED_COLLECTION = "curricula"  # the monitored curriculum is one record of this collection

_TS = {"timestamp": "Date"}

# collection -> {field path: documented type}. Nested fields use dotted paths.
SOURCE_SCHEMA: dict[str, dict[str, str]] = {
    "curricula": {
        "_id": "ObjectId", "curriculumCode": "String", "curriculumName": "String",
        "curriculumYear": "Integer", "version": "Integer", "status": "String", **_TS,
    },
    "persons": {
        "_id": "ObjectId", "title": "String", "firstName": "String", "lastName": "String",
        "fullName": "String", "academicPosition": "String",
        # Import Service SRS §15: true/false once a CV has been processed; absent before that.
        "hasTeachingExperience": "Boolean", **_TS,
    },
    "educations": {
        "_id": "ObjectId", "personId": "ObjectId", "degree": "String", "field": "String",
        "institution": "String", "graduationYear": "Integer", **_TS,
    },
    "appointments": {
        "_id": "ObjectId", "curriculumId": "ObjectId", "personId": "ObjectId", "role": "String",
        "roleName": "String", "effectiveDate": "Date/String", "appointmentOrder": "Object",
        "appointmentOrder.orderNumber": "String", "appointmentOrder.orderDate": "Date/String",
        "status": "String", **_TS,
    },
    "academic_works": {
        "_id": "ObjectId", "personId": "ObjectId", "workType": "String", "title": "String",
        "publicationYear": "Integer", "database": "String", "quartile": "String", **_TS,
    },
    "documents": {
        "_id": "ObjectId", "documentType": "String", "fileType": "String", "fileName": "String",
        "curriculumId": "ObjectId",
        "originalFile": "Object", "originalFile.storage": "String", "originalFile.path": "String",
        "convertedFile": "Object", "convertedFile.storage": "String", "convertedFile.path": "String",
        "extractedText": "Object", "extractedText.storage": "String", "extractedText.path": "String",
        "status": "String", **_TS,
    },
    "data_usages": {
        "_id": "ObjectId", "dataType": "String", "dataId": "ObjectId", "curriculumId": "ObjectId",
        "psCodes": "Array[String]", "roles": "Array[String]", "templateFields": "Array[String]", **_TS,
    },
    "generated_documents": {
        "_id": "ObjectId", "curriculumId": "ObjectId", "fileName": "String", "fileType": "String",
        "generatedFiles": "Array[Object]", "generatedFiles.path": "String", "generatedFiles.timestamp": "Date", **_TS,
    },
}

# collection -> the field that links its records to curricula._id, per the Data Dictionary.
# A collection absent from this table has no declared relationship to a curriculum.
CURRICULUM_LINK: dict[str, str] = {
    "curricula": "_id",
    "appointments": "curriculumId",
    "documents": "curriculumId",
    "data_usages": "curriculumId",
    "generated_documents": "curriculumId",
}


# reference field -> (collection, key) of the record it points at, per the Data Dictionary relationships:
#   appointments/educations/academic_works.personId -> persons._id
#   appointments/documents/data_usages/generated_documents.curriculumId -> curricula._id
REFERENCES: dict[str, tuple[str, str]] = {
    "personId": ("persons", "_id"),
    "curriculumId": ("curricula", "_id"),
}

# collection -> the field that names one of its records on screen (Data Dictionary: persons.fullName
# "ชื่อ-นามสกุลเต็ม", curricula.curriculumCode "รหัสหลักสูตร"). DISPLAY ONLY: no evaluation reads it.
DISPLAY_FIELD: dict[str, str] = {
    "persons": "fullName",
    "curricula": "curriculumCode",
}


def declared_type(collection: str, path: str) -> str | None:
    """The documented type of `collection.path`, or None if the schema does not declare it."""
    if not isinstance(collection, str) or not isinstance(path, str):
        return None
    return SOURCE_SCHEMA.get(collection, {}).get(path)


def is_container(type_name: str) -> bool:
    """Object and Array values are not scalars (they cannot be counted as distinct values)."""
    return type_name == "Object" or type_name.startswith("Array")
