from dataclasses import dataclass, field

from app.models.schemas import DataGroup, SummaryItem
from app.models.status import Status


@dataclass
class Outcome:
    status: Status
    summary: list[SummaryItem] = field(default_factory=list)
    found: list[DataGroup] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
