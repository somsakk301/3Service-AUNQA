"""User review (SET 5, project owner 2026-09-26).

A PS whose configuration asks for a review by the user — `review: {required: true, reviewByUser: true,
allowManualResult: [...]}` — takes the reviewer's choice among the configured statuses. The choice is kept apart
from the result: the PS status stays the engine's; both readinesses count the choice (`PSResult.readiness_status()`,
project owner 2026-09-27). Nothing here names a PS; which PS takes a review is the configuration's.
"""
from app.models.status import Status
from app.repositories.base import Document


def options(requirement: Document) -> list[Status] | None:
    """The statuses a reviewer may choose, in the configured order; None when the PS takes no user review
    (or its review block is not one the specification defines)."""
    cfg = requirement.get("config")
    review = cfg.get("review") if isinstance(cfg, dict) else None
    if not isinstance(review, dict) or review.get("required") is not True or review.get("reviewByUser") is not True:
        return None
    allowed = review.get("allowManualResult")
    if not isinstance(allowed, list) or not allowed:
        return None
    statuses = [next((s for s in Status if s.value == value), None) for value in allowed]
    return None if None in statuses else list(dict.fromkeys(statuses))
