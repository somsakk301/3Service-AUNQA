"""Monitor-owned persistence (project owner, 2026-09-26).

One collection, `monitoring_results`, keyed by curriculumId + psCode. It is the only data Mornitor writes;
Source Data and Configuration stay read only. A record holds, for one PS:
{curriculumId, psCode, verification: {verified: true, verifiedAt}, review: {status, recordedAt, recordedBy},
 result: {status, evaluatedAt}}.
`result` is the persisted monitoring result: the engine's status when the user last saved (current state, no
history; it stays as saved when source data change). Writing one part never removes another, and nothing
here is read back by the engine. `review.recordedBy` (project owner, 2026-10-04: Authentication) is the
signed-in identity that saved the review, verified by the session cookie, never a name the caller sent; it is
absent on a review saved before sessions existed (migration: `review.reviewedAt` -> `review.recordedAt`,
no `recordedBy` invented for that data).
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Protocol

from app.models.status import Status
from app.repositories.base import Document


@dataclass(frozen=True)
class RecordedBy:
    """Who saved a review, at the repository layer (kept apart from the API's own RecordedBy model)."""
    user_id: str
    name: str


class MonitoringResultAdapter(Protocol):
    def read(self, curriculum_id: Any) -> list[Document]: ...

    def set_verified(self, curriculum_id: Any, ps_code: str, verified_at: datetime) -> None:
        """Idempotent: the first verification of curriculumId + psCode stands; no second record."""

    def set_review(self, curriculum_id: Any, ps_code: str, status: str, recorded_at: datetime,
                   recorded_by: dict[str, str] | None = None) -> None:
        """Sets the review of the curriculumId + psCode record (created if absent); nothing else of it changes."""

    def set_results(self, curriculum_id: Any, statuses: dict[str, str], evaluated_at: datetime) -> None:
        """One write sets `result` of the record of every PS listed (created if absent); nothing else of them changes."""


@dataclass(frozen=True)
class MonitorRecord:
    """What the store holds for one PS; absent parts are None."""
    verified_at: datetime | None = None
    verified: bool = False
    review_status: Status | None = None
    recorded_at: datetime | None = None
    recorded_by: RecordedBy | None = None
    result_status: Status | None = None
    evaluated_at: datetime | None = None


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)   # MongoDB returns UTC without zone


def _status(value: Any) -> Status | None:
    return next((s for s in Status if s.value == value), None)


def _recorded_by(review: Document) -> RecordedBy | None:
    by = review.get("recordedBy")
    if not isinstance(by, dict) or not isinstance(by.get("userId"), str) or not isinstance(by.get("name"), str):
        return None
    return RecordedBy(user_id=by["userId"], name=by["name"])


def _record(doc: Document) -> MonitorRecord:
    verification = doc.get("verification") if isinstance(doc.get("verification"), dict) else {}
    review = doc.get("review") if isinstance(doc.get("review"), dict) else {}
    result = doc.get("result") if isinstance(doc.get("result"), dict) else {}
    verified = verification.get("verified") is True
    status = _status(review.get("status"))
    saved = _status(result.get("status"))
    return MonitorRecord(verified_at=_utc(verification.get("verifiedAt")) if verified else None, verified=verified,
                         review_status=status, recorded_at=_utc(review.get("recordedAt")) if status else None,
                         recorded_by=_recorded_by(review) if status else None,
                         result_status=saved, evaluated_at=_utc(result.get("evaluatedAt")) if saved else None)


class MonitoringResultRepository:
    def __init__(self, adapter: MonitoringResultAdapter, clock: Callable[[], datetime] | None = None) -> None:
        self._adapter = adapter
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def records(self, curriculum_id: Any) -> dict[str, MonitorRecord]:
        """psCode -> what the store holds, for every PS of the curriculum that has a record."""
        found = {}
        for doc in self._adapter.read(curriculum_id):
            code = str(doc.get("psCode"))
            found[code] = _record(doc)
        return found

    def verify(self, curriculum_id: Any, ps_code: str) -> None:
        self._adapter.set_verified(curriculum_id, ps_code, self._clock())

    def review(self, curriculum_id: Any, ps_code: str, status: Status, recorded_by: RecordedBy | None = None) -> None:
        """The time is the server's own (never the caller's); `recorded_by` is the signed-in identity the
        session cookie verified (None: no session service is wired, or the caller supplied none)."""
        by = {"userId": recorded_by.user_id, "name": recorded_by.name} if recorded_by is not None else None
        self._adapter.set_review(curriculum_id, ps_code, status.value, self._clock(), by)

    def save_results(self, curriculum_id: Any, statuses: dict[str, Status]) -> None:
        """psCode -> the status the engine gave it now; one server time for the whole save."""
        self._adapter.set_results(curriculum_id, {code: s.value for code, s in statuses.items()}, self._clock())
