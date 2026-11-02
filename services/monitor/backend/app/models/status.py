from enum import Enum


class Status(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    REVIEW = "REVIEW"
    NA = "N/A"


class Readiness(str, Enum):
    """Generation readiness: the only two values the project owner defined (2026-09-26)."""
    READY = "READY"
    NOT_READY = "NOT_READY"
