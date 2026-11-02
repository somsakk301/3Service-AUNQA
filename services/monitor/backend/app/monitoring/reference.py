"""Named reference values used by configuration (`comparison.reference`, relative time windows).

The engine knows no reference by name. A `ReferenceSource` resolves a name to an integer at run
time, says which reference anchors a relative time window, and puts a stored year into the calendar
of that anchor. Production wires the runtime resolver in `app.references`; tests inject fixed values.
A source that defines nothing reports every name as a SPEC GAP.
"""
from typing import Protocol

from app.monitoring.helpers import SpecGap


class ReferenceSource(Protocol):
    def resolve(self, name: str) -> int: ...

    def period_anchor(self) -> int: ...

    def in_anchor_calendar(self, year: int) -> int: ...


class UndefinedReferences:
    def resolve(self, name: str) -> int:
        raise SpecGap(f"reference '{name}' has no definition in the specification (including its calendar, if it is a year)")

    def period_anchor(self) -> int:
        raise SpecGap("a relative time window needs a reference value, and none is defined")

    def in_anchor_calendar(self, year: int) -> int:
        return year          # no calendar is defined, so none is converted
