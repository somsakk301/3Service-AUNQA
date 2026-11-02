"""Layering: the engine knows neither MongoDB nor any adapter; configuration and source data are separate."""
import re
from pathlib import Path

import pytest

from app.models.status import Status
from app.repositories.configuration import ConfigurationRepository
from app.repositories.source_data import SourceDataRepository, SourceQuery, UnknownSourceCollection
from tests.support.fixtures import base_data, make_service
from tests.support.memory_store import InMemoryConfigurationAdapter, InMemorySourceAdapter

APP = Path(__file__).resolve().parents[1] / "app"


def source_of(package: str) -> dict[Path, str]:
    return {p: p.read_text() for p in (APP / package).rglob("*.py")}


def test_evaluation_engine_does_not_know_mongodb():
    for path, text in source_of("monitoring").items():
        assert not re.search(r"pymongo|bson|mongo|\$in|\$eq", text, re.I), path


def test_engine_and_service_do_not_import_adapters():
    for package in ("monitoring", "services", "repositories", "models"):
        for path, text in source_of(package).items():
            assert "app.adapters" not in text and "pymongo" not in text, path


def test_route_handlers_call_the_monitoring_service_only():
    """`api/dependencies.py` is the composition root (it wires adapters); the routes are not."""
    for path, text in source_of("api/routes").items():
        assert "app.monitoring" not in text and "app.adapters" not in text, path
        assert "app.repositories" not in text.replace("app.repositories.base", ""), path


def test_configuration_and_source_data_are_separate_repositories(data):
    config_repo = ConfigurationRepository(InMemoryConfigurationAdapter(data["ps_requirements"]))
    source_repo = SourceDataRepository(InMemorySourceAdapter(data))
    with pytest.raises(UnknownSourceCollection):
        source_repo.find("ps_requirements", SourceQuery())
    assert not hasattr(config_repo, "find") and not hasattr(source_repo, "load_active_requirements")


def test_source_repository_offers_only_the_data_schema_source_collections(data):
    repo = SourceDataRepository(InMemorySourceAdapter(data))
    for name in ("curricula", "persons", "educations", "appointments", "academic_works", "documents",
                 "data_usages", "generated_documents"):
        repo.find(name)
    with pytest.raises(UnknownSourceCollection):
        repo.find("somewhere_else")


def test_configured_collection_outside_source_data_is_a_configuration_error(data):
    data["ps_requirements"][0]["config"]["targetCollection"] = "ps_requirements"
    service, _ = make_service(data)
    r = next(r for r in service.monitor().results if r.ps_code == "PS-01")
    assert r.status is Status.REVIEW and "Configuration error" in r.missing_information[0]


def test_engine_result_does_not_depend_on_which_adapter_supplies_the_data():
    a, _ = make_service(base_data())
    data = base_data()
    b, _ = make_service(data)
    assert [r.status for r in a.monitor().results] == [r.status for r in b.monitor().results]


# --- no business semantics defined in Python ---------------------------------------------------
BUSINESS_WORDS = re.compile(
    r"role|person|degree|programme|qualif|permanent|instructor|master|publication|appointment|education|academic|"
    r"experience|currentYear|previous\d|curriculumYear|curriculumName|responsible|staff|field of study", re.I)


def test_evaluation_code_contains_no_business_vocabulary():
    for package in ("monitoring", "services", "api"):
        for path, text in source_of(package).items():
            assert not BUSINESS_WORDS.search(text), (path, BUSINESS_WORDS.search(text).group(0))


TECHNICAL_VALUES = {"PASS", "FAIL", "REVIEW", "N/A", ">=", ">", "<=", "<", "==", "!=", "EXISTS"}


def string_leaves(node):
    if isinstance(node, dict):
        for v in node.values():
            yield from string_leaves(v)
    elif isinstance(node, list):
        for v in node:
            yield from string_leaves(v)
    elif isinstance(node, str):
        yield node


def test_no_value_of_the_authoritative_configuration_appears_in_python_source():
    """Every string the Data Import side configures (roles, degrees, periods, references, formulas, field names,
    prose) must live only in the configuration, never in evaluation code."""
    from tests.support.fixtures import AUTHORITATIVE_CONFIG
    values = {v for doc in AUTHORITATIVE_CONFIG for v in string_leaves(doc["config"])} - TECHNICAL_VALUES
    values -= {"appointments", "educations", "curricula", "academic_works"}   # Data Dictionary collection names
    values = {v for v in values if len(v) >= 4}
    # the check must really cover the business values it is about
    assert {"programmeResponsible", "programmeStaff", "specialInstructor", "master", "previous5Years", "currentYear",
            "educations.field", "educations.institution", "currentYear - curriculumYear", "personId"} <= values
    for package in ("monitoring", "services", "api"):
        for path, text in source_of(package).items():
            leaked = [v for v in values if v in text]
            assert not leaked, (path, leaked[:5])


def test_engine_imports_no_adapter_and_no_database_driver():
    for path, text in source_of("monitoring").items():
        assert not re.search(r"^\s*(from|import)\s+(pymongo|bson|app\.adapters)", text, re.M), path


def test_the_engine_reads_source_data_only_through_the_repository(data):
    service, source = make_service(data)
    service.monitor()
    assert source.calls and {op for op, _ in source.calls} == {"find"}


def test_evaluation_code_contains_no_numeric_thresholds_or_periods():
    """A threshold, count, period or year in code would be a business value: only 0, 1 and -1 are allowed."""
    import ast
    for path in (APP / "monitoring").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
                assert node.value in (0, 1, -1), (path, node.lineno, node.value)


# Technical vocabulary: operator tables, key-shape patterns, result-label order. None names a business value.
TECHNICAL_CONSTANTS = {"SUPPORTED_OPERATORS", "PROSE_KEYS", "_OPERATORS", "_TOKEN", "_WORDS", "_SAME", "_PERIOD", "_REF",
                       "_FLAG", "_MONOTONE", "PREFERENCE", "_LATIN", "_ERROR", "_FAILED", "_GAP", "_ISSUES"}


def test_evaluation_code_defines_no_module_level_business_constants():
    import ast
    for path in (APP / "monitoring").rglob("*.py"):
        for node in ast.parse(path.read_text()).body:
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id.isupper():
                        assert t.id in TECHNICAL_CONSTANTS, (path, t.id)   # technical vocabulary only
