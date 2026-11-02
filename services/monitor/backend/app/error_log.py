"""Application error logging (SET 8, project owner 2026-09-26): errors only, Python standard logging.

Every record goes to the handler of the `app` logger (stderr): time, level, module, category, message and, for an
error, its traceback. Categories (owner's list): configuration / data source / connection / evaluation / system
error. There is no external-service error: Mornitor makes no outbound call (SET 7). No request, result or
activity is logged; a PS status (PASS / FAIL / REVIEW / N/A) is a result, not an error. Nothing is sent anywhere
else and nothing is written to a database. Connection strings with credentials are masked in the output.
"""
import logging
import re

CONFIGURATION_ERROR = "configuration_error"   # a configuration the engine cannot use (the request still answers)
DATA_SOURCE_ERROR = "data_source_error"       # MongoDB answered with an error (read or Monitor-owned write)
CONNECTION_ERROR = "connection_error"         # MongoDB could not be reached
EVALUATION_ERROR = "evaluation_error"         # the engine failed on one PS (that PS is REVIEW + evaluation_error)
SYSTEM_ERROR = "system_error"                 # any other unexpected exception (HTTP 500)

LOGGER = "app"
FORMAT = "%(asctime)s %(levelname)s %(name)s [%(category)s] %(message)s"
_SECRET = re.compile(r"(\w[\w+.-]*://)[^\s/@:]+:[^\s/@]+@")   # scheme://user:password@ -> scheme://***@


class RedactingFormatter(logging.Formatter):
    """The standard format, with a category on every line and credentials in URLs masked (traceback included)."""

    def format(self, record: logging.LogRecord) -> str:
        if not hasattr(record, "category"):
            record.category = "-"
        return _SECRET.sub(r"\1***@", super().format(record))


def configure_logging() -> None:
    """One stderr handler on the `app` logger, WARNING and above. Safe to call more than once."""
    logger = logging.getLogger(LOGGER)
    if not any(getattr(h, "_mornitor", False) for h in logger.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(RedactingFormatter(FORMAT))
        handler._mornitor = True
        logger.addHandler(handler)
    logger.setLevel(logging.WARNING)


def log_error(logger: logging.Logger, category: str, message: str, *args, level: int = logging.ERROR,
              exc_info=None) -> None:
    """`message` names the operation and safe context only (codes, paths); never documents, bodies or headers."""
    logger.log(level, message, *args, exc_info=exc_info, extra={"category": category})
