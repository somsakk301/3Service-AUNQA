"""Internal extraction result models."""

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ExtractedPage:
    pageNumber: int
    text: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

