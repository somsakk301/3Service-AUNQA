import os
from datetime import datetime
from typing import Any

import pytest
from bson import ObjectId
from pymongo import MongoClient

from app.config import Settings
from app.database.bootstrap import ensure_database_schema
from app.parsing import parse_appointment, parse_curriculum, parse_cv
from app.persistence import DataUsageMapping, StructuredDataError, StructuredDataWriter

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_INTEGRATION_TESTS") != "1",
        reason="set RUN_INTEGRATION_TESTS=1 to use Docker Compose services",
    ),
]


def test_upsert_relationships_and_data_usage_are_srs_compliant() -> None:
    settings = Settings()
    client: MongoClient[dict[str, Any]] = MongoClient(
        settings.mongodb_uri,
        serverSelectionTimeoutMS=5_000,
    )
    database = client.get_default_database()
    ensure_database_schema(database)
    writer = StructuredDataWriter(database)

    curriculum_code = "PHASE6-INTEGRATION"
    person_name = "ผศ. ดร. Phase Six"
    created_ids: dict[str, set[ObjectId]] = {
        "curricula": set(),
        "persons": set(),
        "educations": set(),
        "academic_works": set(),
        "appointments": set(),
        "data_usages": set(),
    }
    try:
        curriculum = parse_curriculum(
            f"""
            curriculumCode: {curriculum_code}
            curriculumName: Phase 6 Test Curriculum
            curriculumYear: 2026
            version: 1
            status: active
            """
        )
        curriculum_id = writer.upsert_curriculum(curriculum)
        created_ids["curricula"].add(curriculum_id)
        assert writer.upsert_curriculum(curriculum) == curriculum_id

        cv = parse_cv(
            f"""
            Full Name: {person_name}
            Education:
            Ph.D. | Computing | Test University | 2020
            M.Sc. | Information Systems | Test University | 2015
            Academic Works:
            Journal | Phase 6 Persistence | 2026 | Scopus | Q1
            """
        )
        first_cv_write = writer.upsert_cv(cv, curriculum_id)
        second_cv_write = writer.upsert_cv(cv, str(curriculum_id))
        created_ids["persons"].add(first_cv_write.personId)
        created_ids["educations"].update(first_cv_write.educationIds)
        created_ids["academic_works"].update(first_cv_write.academicWorkIds)
        assert second_cv_write == first_cv_write
        assert database["persons"].count_documents({"fullName": person_name}) == 1
        assert database["persons"].find_one(
            {"_id": first_cv_write.personId}
        )["hasTeachingExperience"] is False
        assert database["educations"].count_documents(
            {"personId": first_cv_write.personId}
        ) == 2
        assert database["academic_works"].count_documents(
            {"personId": first_cv_write.personId}
        ) == 1

        for collection_name in ("educations", "academic_works"):
            assert all(
                record["personId"] == first_cv_write.personId
                for record in database[collection_name].find(
                    {"personId": first_cv_write.personId}
                )
            )

        appointment = parse_appointment(
            f"""
            Full Name: {person_name}
            Curriculum Code: {curriculum_code}
            role: programmeResponsible
            roleName: Programme Chair
            effectiveDate: 2026-01-01
            orderNumber: P6/2026
            orderDate: 2025-12-01
            status: active
            """
        )
        mismatched_appointment = parse_appointment(
            f"""
            Full Name: {person_name}
            Curriculum Code: OTHER-CURRICULUM
            role: programmeResponsible
            roleName: Programme Chair
            effectiveDate: 2026-01-01
            orderNumber: P6/2026
            orderDate: 2025-12-01
            status: active
            """
        )
        with pytest.raises(StructuredDataError, match="does not match"):
            writer.upsert_appointment(mismatched_appointment, curriculum_id)

        appointment_id = writer.upsert_appointment(appointment, curriculum_id)
        created_ids["appointments"].add(appointment_id)
        assert writer.upsert_appointment(appointment, curriculum_id) == appointment_id
        appointment_record = database["appointments"].find_one(
            {"_id": appointment_id}
        )
        assert appointment_record is not None
        assert appointment_record["curriculumId"] == curriculum_id
        assert appointment_record["personId"] == first_cv_write.personId

        mapping = DataUsageMapping(
            psCodes=["PS-01", "PS-01", "PS-02"],
            roles=["programmeResponsible", "programmeResponsible"],
            templateFields=["person.fullName", "person.fullName"],
        )
        usage_id = writer.upsert_data_usage(
            data_type="person",
            data_id=first_cv_write.personId,
            curriculum_id=curriculum_id,
            mapping=mapping,
        )
        created_ids["data_usages"].add(usage_id)
        assert writer.upsert_data_usage(
            data_type="person",
            data_id=first_cv_write.personId,
            curriculum_id=curriculum_id,
            mapping=mapping,
        ) == usage_id
        usage = database["data_usages"].find_one({"_id": usage_id})
        assert usage is not None
        assert usage["dataId"] == first_cv_write.personId
        assert usage["curriculumId"] == curriculum_id
        assert usage["psCodes"] == ["PS-01", "PS-02"]
        assert usage["roles"] == ["programmeResponsible"]

        assert database["curricula"].count_documents(
            {"curriculumCode": curriculum_code}
        ) == 1
        assert database["appointments"].count_documents(
            {"_id": appointment_id}
        ) == 1
        assert database["data_usages"].count_documents({"_id": usage_id}) == 1
        for collection_name, ids in created_ids.items():
            for record_id in ids:
                record = database[collection_name].find_one({"_id": record_id})
                assert record is not None
                assert isinstance(record["timestamp"], datetime)
    finally:
        for collection_name in (
            "data_usages",
            "appointments",
            "academic_works",
            "educations",
            "persons",
            "curricula",
        ):
            ids = list(created_ids[collection_name])
            if ids:
                database[collection_name].delete_many({"_id": {"$in": ids}})
        client.close()


def test_invalid_object_id_relationship_and_ps_code_are_rejected() -> None:
    settings = Settings()
    client: MongoClient[dict[str, Any]] = MongoClient(settings.mongodb_uri)
    writer = StructuredDataWriter(client.get_default_database())
    try:
        cv = parse_cv(
            """
            Full Name: Dr. Missing Curriculum
            Education:
            Ph.D. | Computing | Test University | 2020
            Academic Works:
            Journal | Validation | 2026 | Scopus | Q1
            """
        )
        with pytest.raises(StructuredDataError, match="curriculumId"):
            writer.upsert_cv(cv, "not-an-object-id")

        with pytest.raises(StructuredDataError, match="PS-01 through PS-09"):
            writer.upsert_data_usage(
                data_type="person",
                data_id=ObjectId(),
                curriculum_id=ObjectId(),
                mapping=DataUsageMapping(
                    psCodes=["PS-10"], roles=[], templateFields=[]
                ),
            )
    finally:
        client.close()


def test_person_identity_ignores_missing_academic_position() -> None:
    settings = Settings()
    client: MongoClient[dict[str, Any]] = MongoClient(settings.mongodb_uri)
    database = client.get_default_database()
    ensure_database_schema(database)
    writer = StructuredDataWriter(database)
    suffix = str(ObjectId())
    first_name = f"Identity-{suffix}"
    last_name = "Merge-Test"
    created_person_id: ObjectId | None = None
    try:
        curriculum_person = parse_cv(
            f"""
            Full Name: Assistant Professor Dr. {first_name} {last_name}
            Education:
            Ph.D. | Computing | Test University | 2020
            Academic Works:
            Journal | Identity Seed | 2026 | Scopus | Q1
            """
        ).person
        cv_person = parse_cv(
            f"""
            Full Name: Dr. {first_name} {last_name}
            Education:
            Ph.D. | Computing | Test University | 2020
            Academic Works:
            Journal | Identity CV | 2026 | Scopus | Q1
            Teaching Experience:
            Software Engineering | Test University | 2020-2026
            """
        ).person

        created_person_id = writer.upsert_person(curriculum_person)
        assert writer.upsert_person(cv_person) == created_person_id
        stored = database["persons"].find_one({"_id": created_person_id})
        assert stored is not None
        assert stored["fullName"] == curriculum_person.fullName
        assert stored["academicPosition"] == "Assistant Professor"
        assert stored["hasTeachingExperience"] is True
        assert database["persons"].count_documents(
            {"firstName": first_name, "lastName": last_name}
        ) == 1
    finally:
        if created_person_id is not None:
            database["persons"].delete_one({"_id": created_person_id})
        client.close()
