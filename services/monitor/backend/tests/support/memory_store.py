"""TEST-ONLY in-memory implementations of the repository adapters.

They implement the same ports as the MongoDB adapters in app/adapters/mongo.py.
Passing tests against them is NOT evidence that MongoDB integration works; see
test_backend_parity.py for the real-MongoDB comparison.
"""
import copy
from typing import Any

from app.repositories.base import DataSourceError, Document
from app.repositories.source_data import SourceQuery


class InMemoryUserAdapter:
    """TEST-ONLY stand-in for the Monitor-owned `users` collection (app/adapters/auth.py)."""

    def __init__(self, users: dict[str, Document] | None = None) -> None:
        self.users = users if users is not None else {}   # keyed by username, each doc needs an "_id"

    def find_by_username(self, username: str) -> Document | None:
        doc = self.users.get(username)
        return copy.deepcopy(doc) if doc is not None else None

    def find_by_id(self, user_id: str) -> Document | None:
        doc = next((d for d in self.users.values() if str(d.get("_id")) == user_id), None)
        return copy.deepcopy(doc) if doc is not None else None

    def set_sessions_invalid_before(self, user_id: str, at: Any) -> None:
        doc = next((d for d in self.users.values() if str(d.get("_id")) == user_id), None)
        if doc is not None:
            doc["sessionsInvalidBefore"] = at


class InMemorySourceAdapter:
    def __init__(self, data: dict[str, list[Document]]) -> None:
        self.data = data
        self.calls: list[tuple[str, str]] = []

    def find(self, collection: str, query: SourceQuery) -> list[Document]:
        self.calls.append(("find", collection))
        out = []
        for doc in self.data.get(collection, []):
            if all(doc.get(k) == v for k, v in query.equals.items()) and \
               all(doc.get(k) in list(vals) for k, vals in query.any_of.items()):
                out.append(copy.deepcopy(doc))
        return out


class InMemoryConfigurationAdapter:
    def __init__(self, docs: list[Document], leak_inactive: bool = False) -> None:
        self.docs = docs
        self.leak_inactive = leak_inactive
        self.calls: list[str] = []

    def read_active(self) -> list[Document]:
        self.calls.append("read_active")
        return [copy.deepcopy(d) for d in self.docs if self.leak_inactive or d.get("active") is True]

    def read_by_code(self, ps_code: str) -> Document | None:
        self.calls.append("read_by_code")
        return next((copy.deepcopy(d) for d in self.docs if d.get("psCode") == ps_code), None)

    def read_by_type(self, config_type: str) -> list[Document]:
        self.calls.append("read_by_type")
        return [copy.deepcopy(d) for d in self.docs if d.get("configType") == config_type]


class FailingSourceAdapter:
    def find(self, collection: str, query: SourceQuery) -> list[Document]:
        raise DataSourceError("connection refused")


class FailingConfigurationAdapter:
    def read_active(self) -> list[Document]:
        raise DataSourceError("connection refused")

    def read_by_code(self, ps_code: str) -> Any:
        raise DataSourceError("connection refused")

    def read_by_type(self, config_type: str) -> list[Document]:
        raise DataSourceError("connection refused")


class InMemoryMonitoringResultAdapter:
    """TEST-ONLY stand-in for the Monitor-owned `monitoring_results` collection (same semantics as
    MongoMonitoringResultAdapter: one record per curriculumId + psCode; the first verification stands;
    a review is set in place)."""

    def __init__(self, docs: list[Document] | None = None, fail: bool = False) -> None:
        self.docs = docs if docs is not None else []
        self.fail = fail
        self.calls: list[str] = []

    def read(self, curriculum_id: Any) -> list[Document]:
        self.calls.append("read")
        if self.fail:
            raise DataSourceError("connection refused")
        return [copy.deepcopy(d) for d in self.docs if d.get("curriculumId") == curriculum_id]

    def set_verified(self, curriculum_id: Any, ps_code: str, verified_at: Any) -> None:
        self.calls.append("set_verified")
        if self.fail:
            raise DataSourceError("connection refused")
        doc = next((d for d in self.docs if d.get("curriculumId") == curriculum_id and d.get("psCode") == ps_code), None)
        if doc is None:
            doc = {"curriculumId": curriculum_id, "psCode": ps_code}
            self.docs.append(doc)
        if doc.get("verification", {}).get("verified") is not True:
            doc["verification"] = {"verified": True, "verifiedAt": verified_at}

    def set_review(self, curriculum_id: Any, ps_code: str, status: str, recorded_at: Any,
                   recorded_by: dict[str, str] | None = None) -> None:
        self.calls.append("set_review")
        if self.fail:
            raise DataSourceError("connection refused")
        doc = next((d for d in self.docs if d.get("curriculumId") == curriculum_id and d.get("psCode") == ps_code), None)
        if doc is None:
            doc = {"curriculumId": curriculum_id, "psCode": ps_code}
            self.docs.append(doc)
        review: dict[str, Any] = {"status": status, "recordedAt": recorded_at}
        if recorded_by is not None:
            review["recordedBy"] = recorded_by
        doc["review"] = review

    def set_results(self, curriculum_id: Any, statuses: dict[str, str], evaluated_at: Any) -> None:
        self.calls.append("set_results")
        if self.fail:
            raise DataSourceError("connection refused")
        for code, status in statuses.items():
            doc = next((d for d in self.docs if d.get("curriculumId") == curriculum_id and d.get("psCode") == code), None)
            if doc is None:
                doc = {"curriculumId": curriculum_id, "psCode": code}
                self.docs.append(doc)
            doc["result"] = {"status": status, "evaluatedAt": evaluated_at}
