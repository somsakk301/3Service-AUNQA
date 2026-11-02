"""Manual review results.

A configuration may require a review by the user and list the statuses the user may choose. The
specification defines no store for such a result and Mornitor never writes, so the result is read
through this port; production supplies none (the PS stays at the configured review status).
"""
from typing import Protocol


class ManualResultSource(Protocol):
    def get(self, key: str) -> str | None: ...


class NoManualResults:
    def get(self, key: str) -> str | None:
        return None
