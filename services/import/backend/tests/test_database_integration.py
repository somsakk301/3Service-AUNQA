import os
from datetime import datetime, timezone

import pytest
from bson import ObjectId
from pymongo import MongoClient
from pymongo.errors import WriteError

from app.config import get_settings
from app.database.bootstrap import ensure_database_schema
from app.database.schema import COLLECTION_SPECS

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_INTEGRATION_TESTS") != "1",
        reason="set RUN_INTEGRATION_TESTS=1 to use Docker Compose MongoDB",
    ),
]


def test_bootstrap_applies_validators_and_indexes_without_generated_documents() -> None:
    settings = get_settings()
    client = MongoClient(settings.mongodb_uri)
    database = client.get_default_database()
    generated_existed_before = "generated_documents" in database.list_collection_names()

    try:
        first_result = ensure_database_schema(database)
        second_result = ensure_database_schema(database)
        collection_names = set(database.list_collection_names())

        assert set(COLLECTION_SPECS).issubset(collection_names)
        assert (
            "generated_documents" in collection_names
        ) is generated_existed_before
        assert set(first_result) == set(COLLECTION_SPECS)
        assert all(not item["created"] for item in second_result.values())

        for collection_name, spec in COLLECTION_SPECS.items():
            options = database[collection_name].options()
            assert options["validationLevel"] == "strict"
            assert options["validationAction"] == "error"
            assert options["validator"]["$jsonSchema"] == spec.schema

            actual_indexes = set(database[collection_name].index_information())
            expected_indexes = {
                index.document["name"] for index in spec.indexes
            }
            assert expected_indexes.issubset(actual_indexes)
    finally:
        client.close()


def test_mongodb_rejects_forbidden_person_role_and_string_relationship() -> None:
    settings = get_settings()
    client = MongoClient(settings.mongodb_uri)
    database = client.get_default_database()
    ensure_database_schema(database)

    try:
        with pytest.raises(WriteError):
            database["persons"].insert_one(
                {
                    "_id": ObjectId(),
                    "title": "Dr.",
                    "firstName": "Schema",
                    "lastName": "Test",
                    "fullName": "Dr. Schema Test",
                    "academicPosition": "Lecturer",
                    "role": "programmeStaff",
                    "sources": [],
                    "timestamp": datetime.now(timezone.utc),
                }
            )

        with pytest.raises(WriteError):
            database["documents"].insert_one(
                {
                    "_id": ObjectId(),
                    "documentType": "cv",
                    "fileType": "pdf",
                    "fileName": "invalid.pdf",
                    "curriculumId": "not-an-object-id",
                    "originalFile": {"storage": "local", "path": "relative.pdf"},
                    "convertedFile": {"storage": "local", "path": ""},
                    "extractedText": {"storage": "local", "path": ""},
                    "status": "uploaded",
                    "timestamp": datetime.now(timezone.utc),
                }
            )
    finally:
        client.close()


def test_persons_accepts_only_boolean_teaching_experience_when_present() -> None:
    settings = get_settings()
    client = MongoClient(settings.mongodb_uri)
    database = client.get_default_database()
    ensure_database_schema(database)
    valid_id = ObjectId()
    invalid_id = ObjectId()

    try:
        database["persons"].insert_one(
            {
                "_id": valid_id,
                "title": "Dr.",
                "firstName": "Teaching",
                "lastName": "Evidence",
                "fullName": f"Dr. Teaching Evidence {valid_id}",
                "academicPosition": "Lecturer",
                "hasTeachingExperience": True,
                "sources": [],
                "timestamp": datetime.now(timezone.utc),
            }
        )
        assert database["persons"].find_one(
            {"_id": valid_id}
        )["hasTeachingExperience"] is True

        with pytest.raises(WriteError):
            database["persons"].insert_one(
                {
                    "_id": invalid_id,
                    "title": "Dr.",
                    "firstName": "Invalid",
                    "lastName": "Teaching",
                    "fullName": f"Dr. Invalid Teaching {invalid_id}",
                    "academicPosition": "Lecturer",
                    "hasTeachingExperience": "yes",
                    "sources": [],
                    "timestamp": datetime.now(timezone.utc),
                }
            )
    finally:
        database["persons"].delete_many(
            {"_id": {"$in": [valid_id, invalid_id]}}
        )
        client.close()
