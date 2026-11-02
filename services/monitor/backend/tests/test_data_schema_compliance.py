"""The engine reads only collections and fields the Data Schema declares, and never approximates one."""
import pytest

from app.models.source_schema import CURRICULUM_LINK, SOURCE_SCHEMA
from app.models.status import Status
from app.repositories.source_data import SOURCE_COLLECTIONS, SourceQuery
from tests.support.fixtures import add_person, base_data, make_service, oid, results
from tests.support.memory_store import InMemorySourceAdapter


def cfg(data, code):
    return next(d["config"] for d in data["ps_requirements"] if d["psCode"] == code)


def text(r):
    return " | ".join(r.missing_information)


# --- the schema transcription itself ---------------------------------------------------------
def test_source_collections_are_the_data_schema_collections_without_configuration():
    assert set(SOURCE_SCHEMA) == {"curricula", "persons", "educations", "appointments", "academic_works",
                                  "documents", "data_usages", "generated_documents"}
    assert SOURCE_COLLECTIONS == frozenset(SOURCE_SCHEMA) and "ps_requirements" not in SOURCE_COLLECTIONS


def test_curriculum_relationships_are_exactly_those_the_data_schema_states():
    assert CURRICULUM_LINK == {"curricula": "_id", "appointments": "curriculumId", "documents": "curriculumId",
                               "data_usages": "curriculumId", "generated_documents": "curriculumId"}


def test_display_references_are_data_schema_relationships():
    from app.models.source_schema import DISPLAY_FIELD, REFERENCES
    assert REFERENCES == {"personId": ("persons", "_id"), "curriculumId": ("curricula", "_id")}
    for ref, (collection, key) in REFERENCES.items():
        assert key in SOURCE_SCHEMA[collection] and any(ref in fields for fields in SOURCE_SCHEMA.values())
    for collection, name in DISPLAY_FIELD.items():
        assert name in SOURCE_SCHEMA[collection]


def test_test_fixture_documents_use_only_declared_fields():
    data = base_data()
    for collection, docs in data.items():
        if collection in SOURCE_SCHEMA:
            for doc in docs:
                top_level = {k for k in doc}
                assert top_level <= {p for p in SOURCE_SCHEMA[collection] if "." not in p}, (collection, top_level)


# --- a field the Data Schema does not declare is a SPEC GAP, never a guess -----------------------
@pytest.mark.parametrize("mutate", [
    lambda c: c["filter"].update(rol="programmeResponsible") or c["filter"].pop("role"),   # misspelt filter field
    lambda c: c["filter"].update({"$where": "1"}),                                          # not a field at all
    lambda c: c["count"].update(field="personid"),                                          # near-miss of a real field
])
def test_undeclared_field_is_review_with_spec_gap_not_a_wrong_fail(data, mutate):
    mutate(cfg(data, "PS-01"))
    r = results(data)["PS-01"]
    assert r.status is Status.REVIEW and r.data_found == [] and r.traceability == []
    assert "SPEC GAP" in text(r) and "Data Schema declares no field" in text(r)


def test_undeclared_required_field_is_a_spec_gap(data):
    del cfg(data, "PS-04")["role"]["roleNameRequired"]
    cfg(data, "PS-04")["appointmentOrder"]["requiredFields"].append("notInTheData")
    r = results(data)["PS-04"]
    assert r.status is Status.REVIEW and r.traceability == []           # rejected before any record is read
    assert "Data Schema declares no field" in text(r) and "appointmentOrder.notInTheData" in text(r)


def test_undeclared_formula_field_is_a_spec_gap(data):
    cfg(data, "PS-09")["year"]["field"] = "curriculumYearBE"
    cfg(data, "PS-09")["calculation"]["formula"] = "currentYear - curriculumYearBE"
    r = results(data)["PS-09"]
    assert r.status is Status.REVIEW and r.traceability == []
    assert "Data Schema declares no field" in text(r) and "curriculumYearBE" in text(r)


# --- declared collections that the Data Schema declares are readable, scoped by their declared link ------
def with_usages(data, n_here=3, n_other=2):
    cid = data["curricula"][0]["_id"]
    data["data_usages"] = ([{"_id": oid(), "dataType": "education", "dataId": oid(), "curriculumId": cid,
                             "psCodes": ["x"]} for _ in range(n_here)]
                           + [{"_id": oid(), "dataType": "education", "dataId": oid(), "curriculumId": oid()}
                              for _ in range(n_other)])
    return data


def point_ps01_at_data_usages(data, **count):
    c = cfg(data, "PS-01")
    c.update(targetCollection="data_usages", filter={"dataType": "education"},
             count={"field": "dataId", "distinct": True, **count})
    c["condition"]["value"] = 3


def test_data_usages_are_readable_and_scoped_to_the_monitored_curriculum(data):
    with_usages(data)
    point_ps01_at_data_usages(data)
    assert results(data)["PS-01"].status is Status.PASS          # 3 here; the 2 of another curriculum are not counted
    cfg(data, "PS-01")["condition"]["value"] = 4
    assert results(data)["PS-01"].status is Status.FAIL


def test_generated_documents_are_scoped_by_their_declared_link(data):
    cid = data["curricula"][0]["_id"]
    data["generated_documents"] = [{"_id": oid(), "curriculumId": cid, "fileName": "a.md", "fileType": "md"},
                                   {"_id": oid(), "curriculumId": oid(), "fileName": "b.md", "fileType": "md"}]
    c = cfg(data, "PS-01")
    c.update(targetCollection="generated_documents", filter={"fileType": "md"},
             count={"field": "fileName", "distinct": True})
    c["condition"].update(operator="==", value=1)
    assert results(data)["PS-01"].status is Status.PASS


def test_distinct_count_of_an_array_field_is_a_spec_gap_not_a_crash(data):
    with_usages(data)
    point_ps01_at_data_usages(data, field="psCodes")
    r = results(data)["PS-01"]
    assert r.status is Status.REVIEW and "declared as Array[String]" in text(r)


def test_a_field_inside_an_array_is_a_spec_gap(data):
    data["generated_documents"] = [{"_id": oid(), "curriculumId": data["curricula"][0]["_id"], "fileName": "a.md",
                                    "generatedFiles": [{"path": "p", "timestamp": None}]}]
    c = cfg(data, "PS-01")
    c.update(targetCollection="generated_documents", filter={}, count={"field": "generatedFiles.path", "distinct": True})
    assert "lies inside an array" in text(results(data)["PS-01"])


def test_a_nested_declared_field_can_be_counted(data):
    c = cfg(data, "PS-01")
    c["count"]["field"] = "appointmentOrder.orderNumber"
    r = results(data)["PS-01"]
    assert r.missing_information == [] and r.status is Status.FAIL     # one distinct order number < 5


# --- everything the engine asks the source for is declared ----------------------------------------
class RecordingSource(InMemorySourceAdapter):
    def __init__(self, data):
        super().__init__(data)
        self.queries: list[tuple[str, SourceQuery]] = []

    def find(self, collection, query):
        self.queries.append((collection, query))
        return super().find(collection, query)


def test_every_query_uses_a_declared_collection_and_declared_fields(data):
    """Runs the authoritative configuration and derived executable variants, then audits each query."""
    with_usages(data)
    variants = [data]
    executable = base_data()
    del cfg(executable, "PS-04")["role"]["roleNameRequired"]
    variants.append(executable)
    referenced = base_data()                                       # PS-08 reading a referenced record
    add_person(referenced, "specialInstructor")
    cfg(referenced, "PS-08")["experience"]["source"] = "persons.hasTeachingExperience"
    variants.append(referenced)
    for d in variants:
        service, _ = make_service(d)
        recorder = RecordingSource(d)
        service._source._adapter = recorder
        service.monitor()
        assert recorder.queries
        for collection, query in recorder.queries:
            assert collection in SOURCE_SCHEMA, collection
            assert set(query.equals) | set(query.any_of) <= set(SOURCE_SCHEMA[collection]), (collection, query)

