"""MongoDB adapter for the Monitor-owned collection `monitoring_results`.

The ONLY module of the application that writes to a database, and it writes to this collection alone
(architecture test). Source Data and Configuration adapters (`adapters/mongo.py`) keep calling `find` only.
Every write is an upsert of one sub-document (`verification`, `review` or `result`) of the curriculumId + psCode
record, so one never removes another.
"""
from datetime import datetime
from typing import Any

from pymongo import ASCENDING, UpdateOne
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.adapters.mongo import source_error
from app.repositories.base import Document

MONITORING_RESULTS_COLLECTION = "monitoring_results"
_KEY = ("curriculumId", "psCode")   # the logical key the project owner set


def _key(curriculum_id: Any, ps_code: str) -> dict[str, Any]:
    return {"curriculumId": curriculum_id, "psCode": ps_code}


class MongoMonitoringResultAdapter:
    def __init__(self, database: Database) -> None:
        self._collection = database[MONITORING_RESULTS_COLLECTION]

    def read(self, curriculum_id: Any) -> list[Document]:
        try:
            return list(self._collection.find({"curriculumId": curriculum_id}))
        except PyMongoError as exc:
            raise source_error(exc) from exc

    def _ensure_key(self) -> None:
        self._collection.create_index([(k, ASCENDING) for k in _KEY], unique=True, name="_".join(_KEY))

    def set_verified(self, curriculum_id: Any, ps_code: str, verified_at: datetime) -> None:
        key = _key(curriculum_id, ps_code)
        try:
            self._ensure_key()
            # Matches the record unless it is already verified; then the upsert's insert hits the unique
            # key and the first verification stands.
            self._collection.update_one({**key, "verification.verified": {"$ne": True}},
                                        {"$set": {"verification": {"verified": True, "verifiedAt": verified_at}}},
                                        upsert=True)
        except DuplicateKeyError:
            return
        except PyMongoError as exc:
            raise source_error(exc) from exc

    def set_review(self, curriculum_id: Any, ps_code: str, status: str, recorded_at: datetime,
                   recorded_by: dict[str, str] | None = None) -> None:
        key = _key(curriculum_id, ps_code)
        review: dict[str, Any] = {"status": status, "recordedAt": recorded_at}
        if recorded_by is not None:
            review["recordedBy"] = recorded_by
        try:
            self._ensure_key()
            self._collection.update_one(key, {"$set": {"review": review}}, upsert=True)
        except PyMongoError as exc:
            raise source_error(exc) from exc

    def set_results(self, curriculum_id: Any, statuses: dict[str, str], evaluated_at: datetime) -> None:
        """One ordered bulk write: every psCode of the save, or (connection lost first) none."""
        ops = [UpdateOne(_key(curriculum_id, code), {"$set": {"result": {"status": status, "evaluatedAt": evaluated_at}}},
                         upsert=True) for code, status in statuses.items()]
        if not ops:
            return
        try:
            self._ensure_key()
            self._collection.bulk_write(ops, ordered=True)
        except PyMongoError as exc:
            raise source_error(exc) from exc
