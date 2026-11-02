"""API response models (temporary contract, see docs/SPEC_GAPS.md)."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field
from pydantic.alias_generators import to_camel

from app.models.status import Readiness, Status

# Programme Readiness is out of the nine Programme Standards, always (project owner, 2026-09-26): fixed by
# definition, not configured, and never the number of results or configurations.
PROGRAMME_STANDARDS = 9

DataCompleteness = Literal["complete", "incomplete"]
# Why nothing could be decided, when it is not the data (SRS §48/§50). None: the result stands on the data.
Issue = Literal["configuration_error", "evaluation_error", "spec_gap"]


class ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class SummaryItem(ApiModel):
    label: str
    value: str


class DataGroup(ApiModel):
    label: str
    items: list[str]


class Verification(ApiModel):
    found: int | None = None
    verified: bool | None = None           # the user verified this PS's evidence and result; None: no store
    approved: bool | None = None           # not set by verifying (never inferred from verified)
    verified_at: datetime | None = None    # when it was first verified (monitoring_results)


class RecordedBy(ApiModel):
    """Who saved a review: the signed-in identity the session cookie verified (app/services/auth.py), never a
    name the client sent (project owner, 2026-10-04). No role or permission is modelled."""

    user_id: str
    name: str


class UserReview(ApiModel):
    """For a PS whose configuration asks for a review by the user: the statuses the reviewer may choose
    (config review.allowManualResult) and the choice saved in monitoring_results. It is not the PS status,
    which stays the engine's (2026-09-26); both readinesses count it instead of the engine's status once it is
    saved (project owner, 2026-09-27: `PSResult.readiness_status`)."""

    allow_manual_result: list[Status]
    status: Status | None = None            # None: nothing saved yet
    recorded_by: RecordedBy | None = None   # None: nothing saved yet, or saved before sessions existed
    recorded_at: datetime | None = None     # server time of the last save


class PersistedResult(ApiModel):
    """The engine's status of this PS when the user last saved the monitoring result (monitoring_results).
    Current state: the last save replaces the one before, and it stays as saved when source data change, so it
    may differ from `status`. Never fed back to the engine; no readiness reads it (project owner, 2026-09-26)."""

    status: Status
    evaluated_at: datetime | None = None   # server time of that save


class ReviewRequest(ApiModel):
    """POST body of a review: only the chosen status. The time is the server's; other keys are ignored."""
    status: str


class LoginRequest(ApiModel):
    """POST body of a login: a username and password checked against the Monitor-owned `users` collection
    (app/services/auth.py). There is no register request: an account exists only if a seed script made it."""
    username: str
    password: str


class EvidenceItem(ApiModel):
    label: str
    reference: str | None = None
    storage: str | None = None   # the source document's originalFile.storage; None when absent
    path: str | None = None      # the source document's originalFile.path; None when absent


class TraceItem(ApiModel):
    collection: str
    record_id: str
    fields: list[str]
    values: dict[str, str] = {}


class PSResult(ApiModel):
    ps_code: str
    status: Status
    requirement: str | None = None
    checks: list[str]
    data_summary: list[SummaryItem]
    data_found: list[DataGroup]
    verification: Verification
    missing_information: list[str]
    evidence: list[EvidenceItem]
    traceability: list[TraceItem]
    data_completeness: DataCompleteness
    issue: Issue | None = None
    review_required: bool | None = None
    review_by_user: bool | None = None
    review: UserReview | None = None       # only for a PS reviewed by the user (configuration)
    persisted_result: PersistedResult | None = None   # None: never saved (or no Monitor-owned store)

    def readiness_status(self) -> Status:
        """The status both readinesses count (project owner, 2026-09-27): the reviewer's saved choice for a PS the
        configuration has reviewed by the user, else the engine's status. Worked out when readiness is computed;
        `status` stays the engine's, and nothing of this is serialized or stored."""
        if self.review is not None and self.review.status is not None:
            return self.review.status
        return self.status


class CurriculumInfo(ApiModel):
    """Curriculum header for the UI: a projection of Data Dictionary fields, not evaluation logic."""

    curriculum_code: str | None = None
    curriculum_name: str | None = None
    curriculum_year: str | None = None
    version: str | None = None
    status: str | None = None

    @classmethod
    def from_document(cls, doc: dict) -> "CurriculumInfo":
        def text(key: str) -> str | None:
            return None if doc.get(key) is None else str(doc[key])

        return cls(curriculum_code=text("curriculumCode"), curriculum_name=text("curriculumName"),
                   curriculum_year=text("curriculumYear"), version=text("version"), status=text("status"))


class BlockingPS(ApiModel):
    ps_code: str
    status: Status | None = None   # None: the PS has no result


class GenerationReadiness(ApiModel):
    """Whether the PS results allow document generation, as the configuration document decides it."""

    status: Readiness | None = None   # None: the configuration gives no decision (see issue, detail)
    blocking_ps: list[BlockingPS] = Field(default_factory=list, alias="blockingPS")
    issue: Issue | None = None
    detail: str | None = None


class ProgrammeReadiness(ApiModel):
    """PASS count / 9 x 100 (project owner, 2026-09-26). Only PASS counts: FAIL, REVIEW, N/A and a PS without
    a result do not, and the denominator stays 9. The status counted is `PSResult.readiness_status()` (the saved
    user review where there is one, 2026-09-27). Not the generation readiness, which the configuration decides."""

    percentage: float
    pass_count: int
    total_ps: int = Field(alias="totalPS")

    @classmethod
    def of(cls, results: list[PSResult]) -> "ProgrammeReadiness":
        passed = len({r.ps_code for r in results if r.readiness_status() is Status.PASS})   # a PS counts once
        return cls(percentage=round(passed * 100 / PROGRAMME_STANDARDS, 2), pass_count=passed,
                   total_ps=PROGRAMME_STANDARDS)


class MonitorResponse(ApiModel):
    curriculum: CurriculumInfo | None
    overall_status: Status | None = None
    data_completeness: DataCompleteness
    results: list[PSResult]
    generation_readiness: GenerationReadiness

    @computed_field
    @property
    def programme_readiness(self) -> ProgrammeReadiness | None:
        """Aggregated from the results the engine produced; none without a curriculum (nothing monitored)."""
        return None if self.curriculum is None else ProgrammeReadiness.of(self.results)
