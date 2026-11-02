"""Runtime reference values.

Configuration names references (`currentYear`) and relative time windows without saying where
their values come from. This module defines them from the runtime clock, expressed in the
calendar the stored years use. The calendar is an infrastructure setting (`year_offset`): the
Data Schema's example data stores years in the Buddhist era (curriculumYear 2567, publicationYear
2569 next to 2026 timestamps), so the offset from the clock's Gregorian year is a setting, not a
constant of evaluation code.
"""
from datetime import date
from typing import Callable

from app.monitoring.helpers import SpecGap

CURRENT_YEAR = "currentYear"


class RuntimeReferences:
    def __init__(self, year_offset: int, today: Callable[[], date] = date.today) -> None:
        self._offset = year_offset
        self._today = today

    def resolve(self, name: str) -> int:
        if name == CURRENT_YEAR:
            return self._today().year + self._offset
        raise SpecGap(f"reference '{name}' has no definition in the specification")

    def period_anchor(self) -> int:
        """A relative time window ('previous N years') counts back from the current year."""
        return self.resolve(CURRENT_YEAR)

    def in_anchor_calendar(self, year: int) -> int:
        """A stored year in the calendar of `period_anchor` (the stored years' calendar).

        Some records write a year in the clock's Gregorian calendar instead (project owner 2026-09-27: real
        publicationYear values 2022-2026 next to 2564-2569). With a positive offset, a year of the stored calendar
        is later than the clock's current year for anything dated within the last `offset` years, so a year no later
        than the clock's current year is read as a Gregorian year and shifted by the offset. Any other year, and
        every year when the offset is 0 (data already Gregorian), is kept as it is.
        """
        if self._offset > 0 and year <= self._today().year:
            return year + self._offset
        return year
