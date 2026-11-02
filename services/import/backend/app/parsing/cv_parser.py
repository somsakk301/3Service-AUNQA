"""Parser for CV person, education, and academic-work records."""

import re

from app.parsing.common import (
    discard_header_rows,
    require_labeled_value,
    section_rows,
)
from app.parsing.errors import StructuredParsingError
from app.parsing.models import AcademicWorkData, CVParseResult, EducationData, PersonData
from app.parsing.normalization import (
    clean_text,
    normalize_integer,
    normalize_person_name,
    normalize_string,
)

_EDUCATION_HEADINGS = ("Education", "Educations", "การศึกษา", "ประวัติการศึกษา")
_WORK_HEADINGS = ("Academic Work", "Academic Works", "ผลงานวิชาการ")
_TEACHING_EXPERIENCE_HEADINGS = (
    "Teaching Experience",
    "Teaching Experiences",
    "Courses Taught",
    "ประสบการณ์สอน",
    "ประสบการณ์การสอน",
    "รายวิชาที่สอน",
)
_EMPTY_TEACHING_VALUES = {"", "-", "n/a", "no", "none", "ไม่มี", "ไม่ระบุ"}
_NEGATIVE_TEACHING_VALUE_PATTERNS = (
    re.compile(r"^ไม่มี(?:ข้อมูล)?ประสบการณ์(?:การ)?สอน$"),
    re.compile(r"^(?:no|without) teaching experience$", flags=re.IGNORECASE),
)
_TEACHING_HEADER_CELLS = {
    "course",
    "coursename",
    "institution",
    "level",
    "period",
    "role",
    "รายวิชา",
    "สถาบัน",
    "ระดับ",
    "ช่วงเวลา",
    "บทบาท",
}
_TEACHING_EVIDENCE_PATTERNS = (
    re.compile(r"(?:เคยสอน|สอนรายวิชา|ผู้สอนรายวิชา|รายวิชาที่(?:เคย)?สอน)"),
    re.compile(r"\b(?:taught|teaches)\b", flags=re.IGNORECASE),
)
_NUMBERED_HEADING_PREFIX = r"(?:\d+(?:\.\d+)*[.)]?\s*)?"
_THAI_EDUCATION_START = re.compile(
    rf"^{_NUMBERED_HEADING_PREFIX}(?:การศึกษา|ประวัติการศึกษา)(?:\s|\(|:|：|$)",
    flags=re.IGNORECASE,
)
_THAI_EDUCATION_STOP = re.compile(
    rf"^{_NUMBERED_HEADING_PREFIX}ประสบการณ์การทำงาน(?:\s|\(|:|：|$)",
    flags=re.IGNORECASE,
)
_THAI_WORK_START = re.compile(
    r"^(?P<section>[4-9])(?:\.0)?[.)]?\s*ผลงานทางวิชาการ(?:\s|ย้อนหลัง|\(|:|：|$)",
    flags=re.IGNORECASE,
)
_TOP_LEVEL_SECTION = re.compile(r"^(?P<section>\d+)[.)]\s*\S")
_WORK_SUBSECTION = re.compile(
    r"^[4-9]\.(?P<subsection>\d+)[.)]?\s*(?P<label>.*)$",
    flags=re.IGNORECASE,
)
_NUMBERED_WORK = re.compile(
    r"^\(?(?P<number>\d{1,2})\)?[.)]?\s*(?P<content>.*)$"
)
_WORK_DATABASE = re.compile(
    r"(?P<database>[A-Za-z][A-Za-z0-9 .&/_-]*?)\s+(?P<quartile>Q[1-4])\s*$",
    flags=re.IGNORECASE,
)
_THAI_MONTHS = {
    "มกราคม",
    "กุมภาพันธ์",
    "มีนาคม",
    "เมษายน",
    "พฤษภาคม",
    "มิถุนายน",
    "กรกฎาคม",
    "สิงหาคม",
    "กันยายน",
    "ตุลาคม",
    "พฤศจิกายน",
    "ธันวาคม",
}
_JOURNAL_HINTS = (
    "Energy and Buildings",
    "Sensors",
    "Biomedical Signal Processing and Control",
    "Journal of Building Engineering",
    "Symmetry",
    "Environmental Challenges",
    "Ecological Informatics",
    "Building and Environment",
    "IEEE Access",
    "IEEE Journal of Biomedical and Health Informatics",
    "Informatics",
    "Journal of Ambient Intelligence and Humanized Computing",
    "Buildings",
    "Ieee Access",
    "IEEE Internet of Things Journal",
)


def parse_cv(text: str) -> CVParseResult:
    cleaned = clean_text(text)
    raw_name = _cv_name(cleaned)
    name = normalize_person_name(raw_name)

    education_rows = discard_header_rows(
        section_rows(
            cleaned,
            _EDUCATION_HEADINGS,
            (*_WORK_HEADINGS, *_TEACHING_EXPERIENCE_HEADINGS),
        ),
        {"degree", "field", "institution", "graduationYear", "วุฒิ", "สาขา", "สถาบัน", "ปีที่จบ"},
    )
    work_rows = discard_header_rows(
        section_rows(cleaned, _WORK_HEADINGS, _TEACHING_EXPERIENCE_HEADINGS),
        {"workType", "title", "publicationYear", "database", "quartile", "ประเภท", "ชื่อผลงาน", "ปี"},
    )
    if not education_rows:
        education_rows = _university_cv_education_rows(cleaned)
    if not work_rows:
        work_rows = _university_cv_academic_work_rows(cleaned)
    if not education_rows:
        raise StructuredParsingError("CV must contain at least one Education row")
    if not work_rows:
        raise StructuredParsingError("CV must contain at least one AcademicWork row")

    educations = [_parse_education(row) for row in education_rows]
    academic_works = [_parse_academic_work(row) for row in work_rows]
    return CVParseResult(
        person=PersonData(
            **name.__dict__,
            hasTeachingExperience=_has_teaching_experience(cleaned),
        ),
        educations=educations,
        academicWorks=academic_works,
    )


def _cv_name(text: str) -> str:
    try:
        return require_labeled_value(
            text,
            (
                "fullName",
                "Full Name",
                "Name",
                "ชื่อ-นามสกุล",
                "ชื่อ นามสกุล",
                "ชื่อ-สกุล",
            ),
            "fullName",
        )
    except StructuredParsingError:
        match = re.search(
            r"^(?:ชื่อ-นามสกุล|ชื่อ\s+นามสกุล|ชื่อ-สกุล)\s+(.+?)\s*$",
            text,
            flags=re.IGNORECASE | re.MULTILINE,
        )
        if match is not None:
            return normalize_string(match.group(1))

        # Several official CV forms put the person's name directly below the
        # "Curriculum Vitae" heading without a "ชื่อ-สกุล" label.
        lines = [normalize_string(line) for line in text.splitlines()]
        for index, line in enumerate(lines):
            if "curriculum vitae" not in line.casefold():
                continue
            for candidate in lines[index + 1 : index + 9]:
                candidate = re.sub(r"\s*\([^)]*[A-Za-z][^)]*\)\s*$", "", candidate)
                if re.match(
                    r"^(?:ศาสตราจารย์|รองศาสตราจารย์|ผู้ช่วยศาสตราจารย์|"
                    r"อาจารย์|ศ\.|รศ\.|ผศ\.|อ\.|ดร\.|Dr\.)",
                    candidate,
                    flags=re.IGNORECASE,
                ):
                    return normalize_string(candidate)
        raise


def _university_cv_education_rows(text: str) -> list[list[str]]:
    lines = _section_lines(text, _THAI_EDUCATION_START, _THAI_EDUCATION_STOP)
    rows: list[list[str]] = []
    index = 0
    while index + 2 < len(lines):
        degree = normalize_string(lines[index])
        field_and_institution = normalize_string(lines[index + 1])
        year = normalize_string(lines[index + 2])
        split_values = _split_field_institution(field_and_institution)
        if (
            split_values is not None
            and re.fullmatch(r"\d{4}", year)
            and degree.casefold() not in {"คุณวุฒิ", "ปี พ.ศ."}
        ):
            field, institution = split_values
            if degree and field and institution:
                rows.append([degree, field, institution, year])
                index += 3
                continue
        index += 1
    return rows


def _split_field_institution(value: str) -> tuple[str, str] | None:
    if "/" in value:
        field, institution = value.split("/", maxsplit=1)
        return normalize_string(field), normalize_string(institution)
    # Some table extractors remove the visual column boundary. University
    # names remain a reliable boundary between the field and institution.
    match = re.match(
        r"^(?P<field>.+?)\s+(?P<institution>(?:มหาวิทยาลัย|University\b).+)$",
        value,
        flags=re.IGNORECASE,
    )
    if match is None:
        return None
    return (
        normalize_string(match.group("field")),
        normalize_string(match.group("institution")),
    )


def _university_cv_academic_work_rows(text: str) -> list[list[str]]:
    lines = _work_section_lines(text)
    records: list[tuple[str, list[str]]] = []
    current: list[str] | None = None
    current_type = "Journal"
    expected_number = 1

    for line in lines:
        normalized = normalize_string(line)
        subsection = _WORK_SUBSECTION.match(normalized)
        if subsection is not None:
            if current:
                records.append((current_type, current))
            current = None
            expected_number = 1
            current_type = _work_type(subsection.group("label"))
            continue

        numbered = _NUMBERED_WORK.match(normalized)
        if numbered is not None and int(numbered.group("number")) == expected_number:
            if current:
                records.append((current_type, current))
            current = []
            content = normalize_string(numbered.group("content"))
            if content:
                current.append(content)
            expected_number += 1
            continue

        if current is None:
            continue
        if re.fullmatch(r"\d{1,2}", normalized):
            # CHECO criterion numbers and PDF page numbers are metadata, not
            # part of an academic-work citation.
            continue
        current.append(normalized)
    if current:
        records.append((current_type, current))

    rows: list[list[str]] = []
    for work_type, record in records:
        parsed = _academic_work_row(record, work_type)
        if parsed is not None:
            rows.append(parsed)
    return rows


def _academic_work_row(lines: list[str], work_type: str) -> list[str] | None:
    database = ""
    quartile = ""
    year = ""
    citation_parts: list[str] = []

    for line in lines:
        database_match = _WORK_DATABASE.search(line)
        if database_match is not None:
            database = normalize_string(database_match.group("database"))
            quartile = database_match.group("quartile").upper()
            line = normalize_string(line[: database_match.start()])
        thai_year = re.match(r"^(25\d{2})(?:\s+\S.*)?$", line)
        if thai_year is not None and len(line) <= 32:
            year = thai_year.group(1)
            continue
        if line in _THAI_MONTHS or not line:
            continue
        if _is_work_table_header(line):
            continue
        citation_parts.append(line)

    citation = normalize_string(" ".join(citation_parts))
    if not year:
        cited_year = re.search(r"\((19|20)\d{2}\)", citation)
        if cited_year is not None:
            year = cited_year.group(0).strip("()")
    if not (citation and year):
        return None
    return [work_type, _academic_title(citation), year, database, quartile]


def _work_section_lines(text: str) -> list[str]:
    active = False
    section_number = 0
    result: list[str] = []
    for line in text.splitlines():
        normalized = normalize_string(line)
        if not active:
            start = _THAI_WORK_START.match(normalized)
            if start is not None:
                active = True
                section_number = int(start.group("section"))
            continue
        top_level = _TOP_LEVEL_SECTION.match(normalized)
        if top_level is not None and int(top_level.group("section")) > section_number:
            break
        if normalized.startswith("ตารางที่ 1 ตารางเกณฑ์มาตรฐาน"):
            break
        if normalized:
            result.append(normalized)
    return result


def _work_type(label: str) -> str:
    comparable = normalize_string(label).casefold()
    if any(value in comparable for value in ("ประชุม", "conference", "proceeding", "book series")):
        return "Conference"
    return "Journal"


def _is_work_table_header(value: str) -> bool:
    compact = re.sub(r"\s+", "", normalize_string(value)).casefold()
    return compact in {
        "ลำดับ",
        "ลําดับ",
        "บทความวิจัย/บทความวิชาการ",
        "ที่ตีพิมพ์เผยแพร่ในวารสาร",
        "เกณฑ์มาตรฐาน",
        "เกณฑ์มาตรฐาน*",
        "(ระบุข้อ)",
        "การเผยแพร่",
        "ผลงานทางวิชาการ",
        "ปี",
        "เดือน",
    }


def _academic_title(citation: str) -> str:
    year_match = re.search(r"\(\d{4}\)\.\s*", citation)
    without_authors = citation[year_match.end() :] if year_match else citation
    hints = "|".join(re.escape(value) for value in _JOURNAL_HINTS)
    title_match = re.match(rf"(.+?)\.\s+(?=(?:{hints})\b)", without_authors)
    if title_match is not None:
        return normalize_string(title_match.group(1))
    sentence = re.match(r"(.+?)(?:\.\s+|$)", without_authors)
    return normalize_string(sentence.group(1) if sentence else without_authors)


def _section_lines(
    text: str,
    start_pattern: re.Pattern[str],
    stop_pattern: re.Pattern[str],
) -> list[str]:
    active = False
    result: list[str] = []
    for line in text.splitlines():
        normalized = normalize_string(line)
        if not active and start_pattern.match(normalized):
            active = True
            continue
        if active and stop_pattern.match(normalized):
            break
        if active and normalized:
            result.append(normalized)
    return result


def _has_teaching_experience(text: str) -> bool:
    checked_no = re.search(r"(?:☑|✓|✔||\uf0fe)\s*ไม่มี", text)
    if checked_no is not None:
        return False
    checked_yes = re.search(r"(?:☑|✓|✔||\uf0fe)\s*มี", text)
    if checked_yes is not None:
        return True

    heading_set = {
        normalize_string(value).casefold()
        for value in _TEACHING_EXPERIENCE_HEADINGS
    }
    other_heading_set = {
        normalize_string(value).casefold()
        for value in (*_EDUCATION_HEADINGS, *_WORK_HEADINGS)
    }
    active = False

    for line in text.splitlines():
        normalized_line = normalize_string(line)
        comparable = normalized_line.rstrip(":：").casefold()
        heading_without_number = re.sub(
            rf"^{_NUMBERED_HEADING_PREFIX}", "", comparable
        )
        heading_without_note = re.sub(r"\s*\(.*$", "", heading_without_number)
        if comparable in heading_set or heading_without_note in heading_set:
            active = True
            continue
        if active and comparable in other_heading_set:
            active = False
            continue

        for heading in _TEACHING_EXPERIENCE_HEADINGS:
            match = re.match(
                rf"^{re.escape(heading)}\s*[:：]\s*(.*?)\s*$",
                normalized_line,
                flags=re.IGNORECASE,
            )
            if match is not None:
                return _is_teaching_evidence(match.group(1))

        if active and normalized_line:
            cells = {
                normalize_string(value).casefold().replace(" ", "")
                for value in re.split(r"\s*(?:\||\t)\s*", normalized_line)
            }
            if cells.issubset(_TEACHING_HEADER_CELLS):
                continue
            if _is_teaching_evidence(normalized_line):
                return True

    return any(pattern.search(text) for pattern in _TEACHING_EVIDENCE_PATTERNS)


def _is_teaching_evidence(value: str) -> bool:
    normalized = normalize_string(value).casefold()
    if normalized in _EMPTY_TEACHING_VALUES:
        return False
    return not any(
        pattern.fullmatch(normalized)
        for pattern in _NEGATIVE_TEACHING_VALUE_PATTERNS
    )


def _parse_education(row: list[str]) -> EducationData:
    if len(row) != 4:
        raise StructuredParsingError("Each Education row must contain 4 columns")
    return EducationData(
        degree=normalize_string(row[0]),
        field=normalize_string(row[1]),
        institution=normalize_string(row[2]),
        graduationYear=normalize_integer(row[3], "graduationYear"),
    )


def _parse_academic_work(row: list[str]) -> AcademicWorkData:
    if len(row) != 5:
        raise StructuredParsingError("Each AcademicWork row must contain 5 columns")
    return AcademicWorkData(
        workType=normalize_string(row[0]),
        title=normalize_string(row[1]),
        publicationYear=normalize_integer(row[2], "publicationYear"),
        database=normalize_string(row[3]),
        quartile=normalize_string(row[4]).upper(),
    )
