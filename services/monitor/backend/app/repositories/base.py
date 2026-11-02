from typing import Any

Document = dict[str, Any]


class DataSourceError(Exception):
    """A source could not be read (connection or read failure). This is NOT a monitoring FAIL."""


class DataSourceConnectionError(DataSourceError):
    """The database could not be reached at all (a Connection Error, logged apart from other source errors)."""
