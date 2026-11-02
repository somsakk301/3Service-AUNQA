"""Parser for appointment data and natural-key references."""

import re

from app.parsing.common import require_labeled_value
from app.parsing.errors import StructuredParsingError
from app.parsing.models import (
    AppointmentData,
    AppointmentOrderData,
    AppointmentParseResult,
    CurriculumReference,
    PersonReference,
)
from app.parsing.normalization import (
    clean_text,
    normalize_person_name,
    normalize_role,
    normalize_string,
)


def parse_appointment(text: str) -> AppointmentParseResult:
    cleaned = clean_text(text)
    name = normalize_person_name(
        require_labeled_value(
            cleaned,
            ("person", "personName", "Full Name", "ชื่อ-นามสกุล", "ชื่อ นามสกุล"),
            "personReference.fullName",
        )
    )
    curriculum_code = require_labeled_value(
        cleaned,
        ("curriculumCode", "Curriculum Code", "รหัสหลักสูตร"),
        "curriculumReference.curriculumCode",
    )
    role_name = require_labeled_value(
        cleaned, ("roleName", "Role Name", "ชื่อบทบาท"), "roleName"
    )
    return AppointmentParseResult(
        appointment=AppointmentData(
            role=normalize_role(
                require_labeled_value(cleaned, ("role", "บทบาท"), "role")
            ),
            roleName=normalize_string(role_name),
            effectiveDate=normalize_string(
                require_labeled_value(
                    cleaned, ("effectiveDate", "Effective Date", "วันที่มีผล"), "effectiveDate"
                )
            ),
            appointmentOrder=AppointmentOrderData(
                orderNumber=normalize_string(
                    require_labeled_value(
                        cleaned, ("orderNumber", "Order Number", "เลขที่คำสั่ง"), "orderNumber"
                    )
                ),
                orderDate=normalize_string(
                    require_labeled_value(
                        cleaned, ("orderDate", "Order Date", "วันที่คำสั่ง"), "orderDate"
                    )
                ),
            ),
            status=normalize_string(
                require_labeled_value(cleaned, ("status", "สถานะ"), "status")
            ).casefold(),
        ),
        personReference=PersonReference(fullName=name.fullName),
        curriculumReference=CurriculumReference(
            curriculumCode=normalize_string(curriculum_code)
        ),
    )


def parse_appointments(
    text: str,
    *,
    curriculum_code: str | None = None,
) -> list[AppointmentParseResult]:
    """Parse either one labelled appointment or a multi-person Thai order."""

    cleaned = clean_text(text)
    official_results = _parse_thai_appointment_order(
        cleaned,
        curriculum_code=curriculum_code,
    )
    if official_results:
        return official_results
    return [parse_appointment(cleaned)]


def _parse_thai_appointment_order(
    text: str,
    *,
    curriculum_code: str | None,
) -> list[AppointmentParseResult]:
    lines = [normalize_string(line) for line in text.splitlines()]
    responsible_heading = "อาจารย์ผู้รับผิดชอบหลักสูตร"
    staff_heading = "อาจารย์ประจำหลักสูตร"
    responsible_start = _numbered_section_start(lines, responsible_heading)
    staff_start = _numbered_section_start(lines, staff_heading)
    if responsible_start is None or staff_start is None:
        return []
    if responsible_start >= staff_start:
        return []

    code = curriculum_code
    if code is None:
        code = require_labeled_value(
            text,
            ("curriculumCode", "Curriculum Code", "รหัสหลักสูตร"),
            "curriculumReference.curriculumCode",
        )
    order_number = _required_match(
        text,
        r"^ที่\s+(\d+\s*/\s*\d+)\s*$",
        "appointmentOrder.orderNumber",
    ).replace(" ", "")
    order_date = _required_match(
        text,
        r"สั่ง\s*ณ\s*วันที่\s*(\d+\s+[^\d\n]+?\s+(?:พ\.ศ\.\s*)?\d{4})",
        "appointmentOrder.orderDate",
    )
    effective_date = _required_match(
        text,
        r"ทั้งนี้\s*ตั้งแต่\s*วันที่\s*(\d+\s+[^\d\n]+?\s+(?:พ\.ศ\.\s*)?\d{4})",
        "effectiveDate",
    )

    responsible_names = _numbered_names(
        lines[responsible_start:staff_start],
    )
    staff_names = _numbered_names(
        lines[staff_start:],
        stop_prefix="ทั้งนี้",
    )
    if not responsible_names or not staff_names:
        raise StructuredParsingError(
            "Thai appointment order must contain responsible and staff names"
        )

    results: list[AppointmentParseResult] = []
    for role, role_name, names in (
        ("programmeResponsible", responsible_heading, responsible_names),
        ("programmeStaff", staff_heading, staff_names),
    ):
        for raw_name in names:
            name = normalize_person_name(raw_name)
            results.append(
                AppointmentParseResult(
                    appointment=AppointmentData(
                        role=role,
                        roleName=role_name,
                        effectiveDate=effective_date,
                        appointmentOrder=AppointmentOrderData(
                            orderNumber=order_number,
                            orderDate=order_date,
                        ),
                        status="active",
                    ),
                    personReference=PersonReference(fullName=name.fullName),
                    curriculumReference=CurriculumReference(
                        curriculumCode=normalize_string(code)
                    ),
                )
            )
    return results


def _numbered_section_start(lines: list[str], heading: str) -> int | None:
    for index, line in enumerate(lines):
        if line != heading:
            continue
        if any(
            re.match(r"^\d+[.)]\s*\S", candidate)
            for candidate in lines[index + 1 : index + 4]
        ):
            return index + 1
    return None


def _numbered_names(
    lines: list[str],
    *,
    stop_prefix: str | None = None,
) -> list[str]:
    names: list[str] = []
    for line in lines:
        if stop_prefix is not None and line.startswith(stop_prefix):
            break
        match = re.match(r"^\d+[.)]\s*(.+)$", line)
        if match is not None:
            names.append(normalize_string(match.group(1)))
    return names


def _required_match(text: str, pattern: str, field_name: str) -> str:
    match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
    if match is None:
        raise StructuredParsingError(f"Required field was not found: {field_name}")
    return normalize_string(match.group(1))
