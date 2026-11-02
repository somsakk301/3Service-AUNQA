import logging

from app.error_log import CONFIGURATION_ERROR, log_error
from app.models.auth import AuthenticatedUser
from app.models.schemas import CurriculumInfo, EvidenceItem, MonitorResponse, PersistedResult, PSResult
from app.models.schemas import RecordedBy as ApiRecordedBy
from app.models.schemas import UserReview
from app.models.source_schema import CURRICULUM_KEY
from app.monitoring.context import EvaluationContext
from app.monitoring.engine import MonitoringEngine
from app.monitoring.manual import ManualResultSource, NoManualResults
from app.monitoring.reference import ReferenceSource, UndefinedReferences
from app.repositories.base import DataSourceError, Document
from app.repositories.configuration import ConfigurationRepository
from app.repositories.monitoring_results import MonitoringResultRepository, MonitorRecord
from app.repositories.monitoring_results import RecordedBy as StoredRecordedBy
from app.repositories.source_data import SourceDataRepository
from app.services import generation_readiness, user_review
from app.services.evidence import evidence_of


_log = logging.getLogger(__name__)


class CurriculumSelectionUndefined(Exception):
    """More than one curriculum matches and the specification does not say which to monitor."""


class ReviewNotOffered(Exception):
    """The configuration of this PS asks for no review by the user."""


class ReviewStatusNotAllowed(Exception):
    """The chosen status is not among the configuration's allowManualResult."""


class MonitoringService:
    """Load configuration, load source data, hand both to the engine."""

    def __init__(
        self,
        configuration: ConfigurationRepository,
        source: SourceDataRepository,
        references: ReferenceSource | None = None,
        manual: ManualResultSource | None = None,
        engine: MonitoringEngine | None = None,
        results: MonitoringResultRepository | None = None,
    ) -> None:
        self._configuration = configuration
        self._source = source
        self._references = references or UndefinedReferences()
        self._manual = manual or NoManualResults()
        self._engine = engine or MonitoringEngine()
        self._results = results

    def monitor(self, curriculum_code: str | None = None) -> MonitorResponse:
        return self._monitor(curriculum_code)[1]

    def save_results(self, curriculum_code: str | None = None) -> MonitorResponse | None:
        """Persistent Monitoring Result (project owner, 2026-09-26): evaluate now, exactly as GET does, then keep
        each PS's status in the Monitor-owned store with the server time. Current state: this save replaces the
        last one; it stays as saved when source data change. Everything is evaluated before anything is written."""
        curriculum, response = self._monitor(curriculum_code)
        if curriculum is None:
            return None
        if self._results is None:
            raise DataSourceError("no Monitor-owned store is configured")
        self._results.save_results(curriculum.get(CURRICULUM_KEY), {r.ps_code: r.status for r in response.results})
        return self.monitor(curriculum_code)

    def _monitor(self, curriculum_code: str | None) -> tuple[Document | None, MonitorResponse]:
        requirements = self._configuration.load_active_requirements()
        readiness = self._configuration.load_by_type(generation_readiness.CONFIG_TYPE)
        curriculum = self._load_curriculum(curriculum_code)
        if curriculum is None:
            decided = generation_readiness.decide(readiness, requirements, [])
            _log_configuration_errors([], decided)
            return None, MonitorResponse(curriculum=None, data_completeness="complete", results=[],
                                         generation_readiness=decided)
        ctx = self._context(curriculum)
        evidence = evidence_of(curriculum, self._source)
        records = self._records(curriculum)
        results = [_finish(self._engine.evaluate(doc, ctx), evidence, records, user_review.options(doc))
                   for doc in requirements]
        incomplete = any(r.data_completeness == "incomplete" for r in results)
        decided = generation_readiness.decide(readiness, requirements, results)
        _log_configuration_errors(results, decided)
        return curriculum, MonitorResponse(
            curriculum=CurriculumInfo.from_document(curriculum),
            overall_status=None,  # overall-status rule is a SPEC GAP; never computed here
            data_completeness="incomplete" if incomplete else "complete",
            results=results,
            generation_readiness=decided,
        )

    def ps_detail(self, ps_code: str, curriculum_code: str | None = None) -> PSResult | None:
        requirement = self._configuration.get_requirement(ps_code)
        curriculum = self._load_curriculum(curriculum_code)
        if requirement is None or curriculum is None:
            return None
        result = _finish(self._engine.evaluate(requirement, self._context(curriculum)),
                         evidence_of(curriculum, self._source), self._records(curriculum), user_review.options(requirement))
        _log_configuration_errors([result], None)
        return result

    def verify(self, ps_code: str, curriculum_code: str | None = None) -> PSResult | None:
        """The user checked the evidence and result of this PS: recorded in the Monitor-owned store
        (curriculumId + psCode). The result itself is re-evaluated as usual and nothing of it changes."""
        requirement = self._configuration.get_requirement(ps_code)
        curriculum = self._load_curriculum(curriculum_code)
        if requirement is None or curriculum is None:
            return None
        if self._results is None:
            raise DataSourceError("no Monitor-owned store is configured")
        self._results.verify(curriculum.get(CURRICULUM_KEY), ps_code)
        return self.ps_detail(ps_code, curriculum_code)

    def review(self, ps_code: str, status: str, curriculum_code: str | None = None, *,
              recorded_by: AuthenticatedUser | None = None) -> PSResult | None:
        """The reviewer's choice for a PS whose configuration asks for a review by the user, kept in the
        Monitor-owned store (curriculumId + psCode) together with who recorded it (`recorded_by`: the
        session's own identity, verified by the caller before this is reached — never a name this method is
        asked to trust). The PS status stays the engine's; nothing is decided here."""
        requirement = self._configuration.get_requirement(ps_code)
        curriculum = self._load_curriculum(curriculum_code)
        if requirement is None or curriculum is None:
            return None
        allowed = user_review.options(requirement)
        if allowed is None:
            raise ReviewNotOffered(f"{ps_code} takes no review by the user in its configuration")
        chosen = next((s for s in allowed if s.value == status), None)
        if chosen is None:
            raise ReviewStatusNotAllowed(f"{status!r} is not among the configured allowManualResult {[s.value for s in allowed]}")
        if self._results is None:
            raise DataSourceError("no Monitor-owned store is configured")
        by = StoredRecordedBy(user_id=recorded_by.user_id, name=recorded_by.name) if recorded_by is not None else None
        self._results.review(curriculum.get(CURRICULUM_KEY), ps_code, chosen, by)
        return self.ps_detail(ps_code, curriculum_code)

    def _records(self, curriculum: Document) -> dict[str, MonitorRecord] | None:
        return None if self._results is None else self._results.records(curriculum.get(CURRICULUM_KEY))

    def _context(self, curriculum: Document) -> EvaluationContext:
        return EvaluationContext(curriculum, self._source, self._references, self._manual)

    def _load_curriculum(self, code: str | None) -> Document | None:
        found = self._source.find_curricula(code)
        if len(found) > 1:
            raise CurriculumSelectionUndefined(
                f"SPEC GAP: {len(found)} curricula match and the specification does not define which one to monitor; "
                "request one with curriculumCode")
        return found[0] if found else None


def _log_configuration_errors(results: list[PSResult], readiness) -> None:
    """A configuration the engine cannot use is logged (WARNING, Configuration Error): the request still answers,
    with REVIEW + configuration_error. A PS status itself is never logged."""
    for result in results:
        if result.issue == "configuration_error":
            log_error(_log, CONFIGURATION_ERROR, "configuration of %s cannot be used: %s", result.ps_code,
                      "; ".join(result.missing_information), level=logging.WARNING)
    if readiness is not None and readiness.issue == "configuration_error":
        log_error(_log, CONFIGURATION_ERROR, "generation readiness configuration cannot be used: %s", readiness.detail,
                  level=logging.WARNING)


def _finish(result: PSResult, evidence: list[EvidenceItem], records: dict[str, MonitorRecord] | None,
            review_options: list | None) -> PSResult:
    """The curriculum's documents, the user's verification, for a PS reviewed by the user the reviewer's choice,
    and the persisted result, next to what the engine found. The status and every other field stay the engine's:
    nothing stored is fed back to it. Without a Monitor-owned store the verification stays unknown (null) and
    nothing stored is read."""
    update: dict = {"evidence": [*result.evidence, *evidence]}
    record = MonitorRecord() if records is None else records.get(result.ps_code, MonitorRecord())
    if records is not None:
        update["verification"] = result.verification.model_copy(
            update={"verified": record.verified, "verified_at": record.verified_at})
        if record.result_status is not None:
            update["persisted_result"] = PersistedResult(status=record.result_status, evaluated_at=record.evaluated_at)
    if review_options is not None:
        by = ApiRecordedBy(user_id=record.recorded_by.user_id, name=record.recorded_by.name) \
            if record.recorded_by is not None else None
        update["review"] = UserReview(allow_manual_result=review_options, status=record.review_status,
                                      recorded_by=by, recorded_at=record.recorded_at)
    return result.model_copy(update=update)
