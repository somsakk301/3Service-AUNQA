"""Shared helpers for labelled text and extracted table rows."""

import re
from collections.abc import Iterable

from app.parsing.errors import StructuredParsingError
from app.parsing.normalization import clean_text, normalize_string


def require_labeled_value(
    text: str,
    labels: Iterable[str],
    field_name: str,
) -> str:
    value = optional_labeled_value(text, labels)
    if value is None or not value:
        raise StructuredParsingError(f"Required field was not found: {field_name}")
    return value


def optional_labeled_value(text: str, labels: Iterable[str]) -> str | None:
    alternatives = "|".join(re.escape(label) for label in labels)
    match = re.search(
        rf"^(?:{alternatives})\s*[:：]\s*(.+?)\s*$",
        text,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    return normalize_string(match.group(1)) if match is not None else None


def section_rows(
    text: str,
    headings: Iterable[str],
    stop_headings: Iterable[str],
) -> list[list[str]]:
    """Return pipe/tab rows inside a heading-delimited section."""
    cleaned = clean_text(text)
    heading_set = {normalize_string(value).casefold() for value in headings}
    stop_set = {normalize_string(value).casefold() for value in stop_headings}
    active = False
    rows: list[list[str]] = []
    for line in cleaned.splitlines():
        comparable = normalize_string(line).rstrip(":：").casefold()
        if comparable in heading_set:
            active = True
            continue
        if active and comparable in stop_set:
            break
        if not active or not line:
            continue
        columns = [normalize_string(value) for value in re.split(r"\s*(?:\||\t)\s*", line)]
        if len(columns) > 1:
            rows.append(columns)
    return rows


def discard_header_rows(rows: list[list[str]], header_words: set[str]) -> list[list[str]]:
    normalized_headers = {word.casefold() for word in header_words}
    return [
        row
        for row in rows
        if not any(cell.casefold() in normalized_headers for cell in row)
    ]
