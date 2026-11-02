"""Parser for curriculum documents (SRS section 24)."""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from app.parsing.common import optional_labeled_value, require_labeled_value
from app.parsing.errors import StructuredParsingError
from app.parsing.models import CurriculumData, EducationData, PersonData
from app.parsing.normalization import (
    clean_text,
    normalize_integer,
    normalize_person_name,
    normalize_string,
)


@dataclass(frozen=True)
class CurriculumPersonSeed:
    """Person and education facts present inside a curriculum document."""

    person: PersonData
    educations: tuple[EducationData, ...]
    roles: tuple[str, ...]


_DEGREE_PATTERN = re.compile(
    r"^(?:ปร\.ด\.|วท\.ม\.|วท\.บ\.|บธ\.บ\.|วศ\.ม\.|วศ\.บ\.|Ph\.D\.)$",
    flags=re.IGNORECASE,
)
_PERSON_PATTERN = re.compile(r"^(?:รศ\.|ผศ\.|อ\.|Dr\.?)", flags=re.IGNORECASE)
_SECTION_PATTERN = re.compile(
    r"^1\.(?P<number>[123])\s+อาจารย์(?P<title>[^\n]*)",
    flags=re.MULTILINE,
)
_TABLE_NOISE_PREFIXES = (
    "ลำดับ",
    "ตำแหน่งทางวิชาการ",
    "ชื่อ-นามสกุล",
    "ชื่อปริญญา",
    "(ให้เรียงตามระดับปริญญา",
    "และปีที่สำเร็จการศึกษา)",
    "สาขาวิชา",
    "ปีพ.ศ. ที่",
    "สำเร็จ",
    "การศึกษา",
    "สถาบันที่สำเร็จการศึกษา",
    "(กรณีสำเร็จการศึกษาจาก",
    "ต่างประเทศให้ระบุประเทศโดย",
    "ใช้ชื่อเต็มและต้องระบุให้ตรงกัน",
    "ทั้งฉบับ)",
    "รายละเอียดเพิ่มเติม",
)


def _multiline_labeled_value(text: str, labels: tuple[str, ...]) -> str | None:
    """Read values where PDF extraction puts the label and colon on separate lines."""
    alternatives = "|".join(re.escape(label) for label in labels)
    match = re.search(
        rf"^(?:{alternatives})\s*[:：]\s*([^\n]+)",
        text,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    return normalize_string(match.group(1)) if match is not None else None


def _curriculum_name(text: str) -> str:
    labels = ("curriculumName", "Curriculum Name", "ชื่อหลักสูตร")
    value = optional_labeled_value(text, labels) or _multiline_labeled_value(text, labels)
    if value:
        return normalize_string(value)

    # Thai TQF/Mor Kor 2 documents commonly wrap the Thai programme name over
    # multiple lines and terminate it with the English-name label.
    match = re.search(
        r"^ชื่อหลักสูตรภาษาไทย\s*[:：]\s*(.+?)^ชื่อหลักสูตรภาษาอังกฤษ\s*[:：]",
        text,
        flags=re.IGNORECASE | re.MULTILINE | re.DOTALL,
    )
    if match is None:
        raise StructuredParsingError("Required field was not found: curriculumName")
    return normalize_string(match.group(1))


def _curriculum_year(text: str) -> str:
    labels = ("curriculumYear", "Curriculum Year", "ปีหลักสูตร")
    value = optional_labeled_value(text, labels) or _multiline_labeled_value(text, labels)
    if value:
        return value
    match = re.search(r"หลักสูตร(?:ใหม่|ปรับปรุง)\s*พ\.?ศ\.?\s*(\d+)", text)
    if match is None:
        raise StructuredParsingError("Required field was not found: curriculumYear")
    return match.group(1)


def parse_curriculum(
    text: str,
    reference: Mapping[str, Any] | None = None,
) -> CurriculumData:
    cleaned = clean_text(text)
    code_labels = ("curriculumCode", "Curriculum Code", "รหัสหลักสูตร")
    code = optional_labeled_value(cleaned, code_labels) or _multiline_labeled_value(
        cleaned, code_labels
    )
    if not code:
        raise StructuredParsingError("Required field was not found: curriculumCode")

    version_value = optional_labeled_value(cleaned, ("version", "ฉบับ", "เวอร์ชัน"))
    status_value = optional_labeled_value(cleaned, ("status", "สถานะ"))
    if version_value is None and reference is not None:
        version_value = str(reference.get("version", ""))
    if status_value is None and reference is not None:
        status_value = str(reference.get("status", ""))

    return CurriculumData(
        curriculumCode=normalize_string(code),
        curriculumName=_curriculum_name(cleaned),
        curriculumYear=normalize_integer(_curriculum_year(cleaned), "curriculumYear"),
        version=normalize_integer(
            version_value
            or require_labeled_value(cleaned, ("version", "ฉบับ", "เวอร์ชัน"), "version"),
            "version",
        ),
        status=normalize_string(
            status_value or require_labeled_value(cleaned, ("status", "สถานะ"), "status")
        ).casefold(),
    )


def parse_curriculum_people(text: str) -> list[CurriculumPersonSeed]:
    """Extract initial Person/Education facts without changing CurriculumData."""
    cleaned = clean_text(text)
    sections = list(_SECTION_PATTERN.finditer(cleaned))
    merged: dict[str, dict[str, Any]] = {}

    for section_index, section in enumerate(sections):
        end = (
            sections[section_index + 1].start()
            if section_index + 1 < len(sections)
            else len(cleaned)
        )
        block = cleaned[section.end() : end]
        role = {
            "1": "programmeResponsible",
            "2": "programmeStaff",
            "3": None,
        }[section.group("number")]
        lines = [line.strip() for line in block.splitlines()]
        name_indexes = [
            index
            for index, line in enumerate(lines)
            if _PERSON_PATTERN.match(line) and len(line.split()) >= 2
        ]

        for name_offset, name_index in enumerate(name_indexes):
            next_name = (
                name_indexes[name_offset + 1]
                if name_offset + 1 < len(name_indexes)
                else len(lines)
            )
            normalized_name = normalize_person_name(lines[name_index])
            person = PersonData(
                title=normalized_name.title,
                firstName=normalized_name.firstName,
                lastName=normalized_name.lastName,
                fullName=normalized_name.fullName,
                academicPosition=normalized_name.academicPosition,
            )
            educations = _parse_educations(lines[name_index + 1 : next_name])
            entry = merged.setdefault(
                person.fullName,
                {"person": person, "educations": {}, "roles": []},
            )
            for education in educations:
                key = (
                    education.degree,
                    education.field,
                    education.institution,
                    education.graduationYear,
                )
                entry["educations"][key] = education
            if role is not None and role not in entry["roles"]:
                entry["roles"].append(role)

    return [
        CurriculumPersonSeed(
            person=entry["person"],
            educations=tuple(entry["educations"].values()),
            roles=tuple(entry["roles"]),
        )
        for entry in merged.values()
    ]


def _parse_educations(lines: list[str]) -> list[EducationData]:
    degree_indexes = [
        index for index, line in enumerate(lines) if _DEGREE_PATTERN.match(line)
    ]
    educations: list[EducationData] = []
    for offset, degree_index in enumerate(degree_indexes):
        end = (
            degree_indexes[offset + 1]
            if offset + 1 < len(degree_indexes)
            else len(lines)
        )
        values = [
            line for line in lines[degree_index + 1 : end] if not _is_table_noise(line)
        ]
        year_index = next(
            (
                index
                for index, value in enumerate(values)
                if re.fullmatch(r"\d{4}", value)
            ),
            None,
        )
        if year_index is None:
            continue
        field = normalize_string(" ".join(values[:year_index]))
        institution = normalize_string(" ".join(values[year_index + 1 :]))
        if not field or not institution:
            continue
        educations.append(
            EducationData(
                degree=normalize_string(lines[degree_index]),
                field=field,
                institution=institution,
                graduationYear=int(values[year_index]),
            )
        )
    return educations


def _is_table_noise(value: str) -> bool:
    normalized = normalize_string(value)
    return (
        not normalized
        or normalized == "ที่"
        or re.fullmatch(r"\d{1,3}", normalized) is not None
        or any(normalized.startswith(prefix) for prefix in _TABLE_NOISE_PREFIXES)
    )
