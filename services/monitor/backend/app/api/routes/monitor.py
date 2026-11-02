"""Temporary API contract (SPEC GAP). GET endpoints read; the POST endpoints record what the user did (save the
monitoring result, a verification, a review) in the Monitor-owned store (never source data or configuration)."""
import logging

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_current_user, get_service
from app.error_log import CONNECTION_ERROR, DATA_SOURCE_ERROR, log_error
from app.models.auth import AuthenticatedUser
from app.models.schemas import MonitorResponse, PSResult, ReviewRequest
from app.repositories.base import DataSourceConnectionError, DataSourceError
from app.services.monitoring_service import (
    CurriculumSelectionUndefined, MonitoringService, ReviewNotOffered, ReviewStatusNotAllowed,
)

router = APIRouter(prefix="/api/monitor")

LOAD_ERROR = "Unable to load monitoring data"
SAVE_ERROR = "Unable to save the verification"
REVIEW_SAVE_ERROR = "Unable to save the review"
RESULTS_SAVE_ERROR = "Unable to save the monitoring result"

_log = logging.getLogger(__name__)


def _unavailable(exc: DataSourceError, detail: str, operation: str, curriculum_code: str | None) -> HTTPException:
    """Logs the database failure (ERROR, traceback) and gives the same 503 as before. Context: the operation and
    the curriculum code only; never a document, body or header."""
    category = CONNECTION_ERROR if isinstance(exc, DataSourceConnectionError) else DATA_SOURCE_ERROR
    log_error(_log, category, "%s failed (curriculumCode=%s): %s", operation, curriculum_code, detail, exc_info=exc)
    return HTTPException(status_code=503, detail=detail)


@router.get("", response_model=MonitorResponse, response_model_by_alias=True)
def get_monitor(curriculumCode: str | None = None, service: MonitoringService = Depends(get_service)):
    try:
        return service.monitor(curriculumCode)
    except DataSourceError as exc:
        raise _unavailable(exc, LOAD_ERROR, "GET /api/monitor", curriculumCode) from None
    except CurriculumSelectionUndefined as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None


@router.post("/results", response_model=MonitorResponse, response_model_by_alias=True)
def post_results(curriculumCode: str | None = None, service: MonitoringService = Depends(get_service)):
    """Persistent Monitoring Result: evaluate now and keep each PS's status. Returns the monitor as GET does."""
    try:
        result = service.save_results(curriculumCode)
    except DataSourceError as exc:
        raise _unavailable(exc, RESULTS_SAVE_ERROR, "POST /api/monitor/results", curriculumCode) from None
    except CurriculumSelectionUndefined as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    if result is None:
        raise HTTPException(status_code=404, detail="No monitoring result")
    return result


@router.get("/ps/{ps_code}", response_model=PSResult, response_model_by_alias=True)
def get_ps(ps_code: str, curriculumCode: str | None = None, service: MonitoringService = Depends(get_service)):
    try:
        result = service.ps_detail(ps_code, curriculumCode)
    except DataSourceError as exc:
        raise _unavailable(exc, LOAD_ERROR, f"GET /api/monitor/ps/{ps_code}", curriculumCode) from None
    except CurriculumSelectionUndefined as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    if result is None:
        raise HTTPException(status_code=404, detail="No monitoring result")
    return result


@router.post("/ps/{ps_code}/verification", response_model=PSResult, response_model_by_alias=True)
def post_verification(ps_code: str, curriculumCode: str | None = None, service: MonitoringService = Depends(get_service)):
    """Idempotent: verifying again keeps the first verification. Returns the PS result as GET does."""
    try:
        result = service.verify(ps_code, curriculumCode)
    except DataSourceError as exc:
        raise _unavailable(exc, SAVE_ERROR, f"POST /api/monitor/ps/{ps_code}/verification", curriculumCode) from None
    except CurriculumSelectionUndefined as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    if result is None:
        raise HTTPException(status_code=404, detail="No monitoring result")
    return result


@router.post("/ps/{ps_code}/review", response_model=PSResult, response_model_by_alias=True)
def post_review(ps_code: str, body: ReviewRequest, curriculumCode: str | None = None,
                service: MonitoringService = Depends(get_service),
                user: AuthenticatedUser = Depends(get_current_user)):
    """The reviewer's choice for a PS whose configuration asks for a review by the user, recorded against the
    session's own identity (never one the body could name). Saving again updates the same record. Returns the
    PS result as GET does; its status stays the engine's. 401 without a valid session."""
    try:
        result = service.review(ps_code, body.status, curriculumCode, recorded_by=user)
    except DataSourceError as exc:
        raise _unavailable(exc, REVIEW_SAVE_ERROR, f"POST /api/monitor/ps/{ps_code}/review", curriculumCode) from None
    except CurriculumSelectionUndefined as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except ReviewNotOffered as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    except ReviewStatusNotAllowed as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    if result is None:
        raise HTTPException(status_code=404, detail="No monitoring result")
    return result
