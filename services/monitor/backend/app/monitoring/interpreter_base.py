from dataclasses import dataclass, field

from app.monitoring.request import GenericExecutionRequest


@dataclass
class Interpretation:
    request: GenericExecutionRequest | None = None
    gaps: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
