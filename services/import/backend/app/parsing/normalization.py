"""Deterministic normalization required before Phase 6 duplicate detection."""

import re
import unicodedata
from dataclasses import dataclass

from app.parsing.errors import StructuredParsingError

_THAI_DIGITS = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")
_THAI_PUA_GLYPHS = str.maketrans(
    {
        "\uf702": "ี",
        "\uf706": "้",
        "\uf70a": "่",
        "\uf70b": "้",
        "\uf70e": "์",
        "\uf710": "ั",
        "\uf712": "็",
        "\uf713": "่",
    }
)
_ACADEMIC_POSITIONS = (
    (r"^ศาสตราจารย์(?:\s+|(?=ดร\.|[\u0e00-\u0e7f]))", "ศ."),
    (r"^รองศาสตราจารย์(?:\s+|(?=ดร\.|[\u0e00-\u0e7f]))", "รศ."),
    (r"^รองศาสตาจารย์(?:\s+|(?=ดร\.|[\u0e00-\u0e7f]))", "รศ."),
    (r"^ผู้ช่วยศาสตราจารย์(?:\s+|(?=ดร\.|[\u0e00-\u0e7f]))", "ผศ."),
    (r"^อาจารย์(?:\s+|(?=ดร\.|[\u0e00-\u0e7f]))", "อ."),
    (r"^ศ(?:\.\s*|\s+)", "ศ."),
    (r"^รศ(?:\.\s*|\s+)", "รศ."),
    (r"^ผศ(?:\.\s*|\s+)", "ผศ."),
    (r"^อ(?:\.\s*|\s+)", "อ."),
    (r"^Professor\s+", "Professor"),
    (r"^Associate\s+Professor\s+", "Associate Professor"),
    (r"^Assistant\s+Professor\s+", "Assistant Professor"),
)
_TITLES = (
    (r"^ดร(?:\.\s*|\s+)", "ดร."),
    (r"^นาย\s+", "นาย"),
    (r"^นางสาว\s+", "นางสาว"),
    (r"^นาง\s+", "นาง"),
    (r"^Dr(?:\.\s*|\s+)", "Dr."),
    (r"^Mr(?:\.\s*|\s+)", "Mr."),
    (r"^Mrs(?:\.\s*|\s+)", "Mrs."),
    (r"^Ms(?:\.\s*|\s+)", "Ms."),
)


@dataclass(frozen=True)
class NormalizedPersonName:
    title: str
    firstName: str
    lastName: str
    fullName: str
    academicPosition: str


def clean_text(value: str) -> str:
    """Normalize Unicode, Thai digits, line endings, and insignificant spacing."""
    # NFC preserves Thai SARA AM as one code point, so normalized text still
    # compares correctly with Thai labels such as "คำสั่ง" and "ประจำ".
    value = (
        unicodedata.normalize("NFC", value)
        .translate(_THAI_DIGITS)
        .translate(_THAI_PUA_GLYPHS)
    )
    value = value.replace("\u00a0", " ").replace("\r\n", "\n").replace("\r", "\n")
    lines = [
        "\t".join(re.sub(r" +", " ", column).strip() for column in line.split("\t"))
        for line in value.split("\n")
    ]
    result: list[str] = []
    for line in lines:
        if line or (result and result[-1]):
            result.append(line)
    return "\n".join(result).strip()


def normalize_string(value: str) -> str:
    return re.sub(r"\s+", " ", clean_text(value)).strip(" \t:：")


def normalize_integer(value: str, field_name: str) -> int:
    normalized = normalize_string(value)
    match = re.search(r"\d+", normalized)
    if match is None:
        raise StructuredParsingError(f"{field_name} must contain an integer")
    return int(match.group())


def normalize_role(value: str) -> str:
    normalized = normalize_string(value).casefold()
    compact = re.sub(r"[\s_-]+", "", normalized)
    responsible = {
        "programmeresponsible",
        "อาจารย์ผู้รับผิดชอบหลักสูตร",
        "ผู้รับผิดชอบหลักสูตร",
    }
    staff = {
        "programmestaff",
        "อาจารย์ประจำหลักสูตร",
        "ประจำหลักสูตร",
    }
    if compact in responsible:
        return "programmeResponsible"
    if compact in staff:
        return "programmeStaff"
    raise StructuredParsingError(
        "role must normalize to programmeResponsible or programmeStaff"
    )


def normalize_person_name(value: str) -> NormalizedPersonName:
    remaining = normalize_string(value)
    academic_position = ""
    title = ""

    # Some documents put the title before the academic position; consume both
    # categories in either order while accepting at most one value per category.
    for _ in range(2):
        if not academic_position:
            match = _consume_prefix(remaining, _ACADEMIC_POSITIONS)
            if match is not None:
                academic_position, remaining = match
                continue
        if not title:
            match = _consume_prefix(remaining, _TITLES)
            if match is not None:
                title, remaining = match
                continue

    name_parts = remaining.split()
    if len(name_parts) < 2:
        raise StructuredParsingError("person name must contain firstName and lastName")
    first_name = " ".join(name_parts[:-1])
    last_name = name_parts[-1]
    full_name = " ".join(
        part for part in (academic_position, title, first_name, last_name) if part
    )
    return NormalizedPersonName(
        title=title,
        firstName=first_name,
        lastName=last_name,
        fullName=full_name,
        academicPosition=academic_position,
    )


def _consume_prefix(
    value: str,
    patterns: tuple[tuple[str, str], ...],
) -> tuple[str, str] | None:
    for pattern, standard in patterns:
        match = re.match(pattern, value, flags=re.IGNORECASE)
        if match is not None:
            return standard, value[match.end() :].strip()
    return None
