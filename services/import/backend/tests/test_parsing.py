import pytest

from app.parsing import (
    parse_appointment,
    parse_appointments,
    parse_curriculum,
    parse_curriculum_people,
    parse_cv,
)
from app.parsing.errors import StructuredParsingError
from app.parsing.normalization import clean_text, normalize_person_name, normalize_role


def test_clean_text_normalizes_unicode_whitespace_and_thai_digits() -> None:
    assert clean_text("  ปี\u00a0 ๒๕๖๗\r\n\r\n  สถานะ  ") == "ปี 2567\n\nสถานะ"


@pytest.mark.parametrize("raw", ["ผศ. ดร. สมชาย ใจดี", "ผศ.ดร.สมชาย ใจดี", "ผศ. ดร สมชาย ใจดี"])
def test_person_name_variants_normalize_to_one_format(raw: str) -> None:
    person = normalize_person_name(raw)
    assert person.academicPosition == "ผศ."
    assert person.title == "ดร."
    assert person.firstName == "สมชาย"
    assert person.lastName == "ใจดี"
    assert person.fullName == "ผศ. ดร. สมชาย ใจดี"


def test_full_thai_academic_position_normalizes_to_abbreviation() -> None:
    person = normalize_person_name("รองศาสตราจารย์ ดร.บูคอรี ซาเหาะ")
    assert person.academicPosition == "รศ."
    assert person.title == "ดร."
    assert person.firstName == "บูคอรี"
    assert person.lastName == "ซาเหาะ"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("อาจารย์ผู้รับผิดชอบหลักสูตร", "programmeResponsible"),
        ("programme_responsible", "programmeResponsible"),
        ("อาจารย์ประจำหลักสูตร", "programmeStaff"),
        ("programme staff", "programmeStaff"),
    ],
)
def test_role_normalization(raw: str, expected: str) -> None:
    assert normalize_role(raw) == expected


def test_unknown_role_is_rejected() -> None:
    with pytest.raises(StructuredParsingError):
        normalize_role("programmeOwner")


def test_parse_curriculum_uses_exact_srs_fields() -> None:
    result = parse_curriculum(
        """
        รหัสหลักสูตร: CS-001
        ชื่อหลักสูตร: วิทยาศาสตรบัณฑิต สาขาวิทยาการคอมพิวเตอร์
        ปีหลักสูตร: ๒๕๖๗
        ฉบับ: ๒
        สถานะ: ACTIVE
        """
    )
    assert result.model_dump() == {
        "curriculumCode": "CS-001",
        "curriculumName": "วิทยาศาสตรบัณฑิต สาขาวิทยาการคอมพิวเตอร์",
        "curriculumYear": 2567,
        "version": 2,
        "status": "active",
    }


def test_parse_curriculum_supports_thai_tqf_pdf_layout_and_reference_defaults() -> None:
    result = parse_curriculum(
        """
        รายละเอียดของหลักสูตร
        (หลักสูตรปรับปรุง พ.ศ. 2570)

        รหัสหลักสูตร

        : 25500231104894

        ชื่อหลักสูตรภาษาไทย
        : หลักสูตรวิทยาศาสตรบัณฑิต

        สาขาเทคโนโลยีสารสนเทศอัจฉริยะ

        ชื่อหลักสูตรภาษาอังกฤษ
        : Bachelor of Science Program in Intelligent Information Technology
        """,
        reference={"version": 1, "status": "active"},
    )
    assert result.model_dump() == {
        "curriculumCode": "25500231104894",
        "curriculumName": "หลักสูตรวิทยาศาสตรบัณฑิต สาขาเทคโนโลยีสารสนเทศอัจฉริยะ",
        "curriculumYear": 2570,
        "version": 1,
        "status": "active",
    }


def test_parse_curriculum_people_deduplicates_roles_and_educations() -> None:
    text = """
    1.1 อาจารย์ผู้รับผิดชอบหลักสูตร จำนวน 1 คน
    ลำดับ
    ตำแหน่งทางวิชาการ ชื่อ-นามสกุล
    1
    ผศ.ดร.สมชาย ใจดี
    ปร.ด.
    วิทยาการคอมพิวเตอร์
    2560
    มหาวิทยาลัยตัวอย่าง

    1.2 อาจารย์ประจำหลักสูตร จำนวน 1 คน
    1
    ผศ. ดร. สมชาย ใจดี
    ปร.ด.
    วิทยาการคอมพิวเตอร์
    2560
    มหาวิทยาลัยตัวอย่าง
    วท.ม.
    การจัดการเทคโนโลยีสารสนเทศ
    2555
    มหาวิทยาลัยทดสอบ

    1.3 อาจารย์ผู้สอน จำนวน 2 คน
    1
    ผศ.ดร.สมชาย ใจดี
    ปร.ด.
    วิทยาการคอมพิวเตอร์
    2560
    มหาวิทยาลัยตัวอย่าง
    2
    Dr.Tran Anh Tuan
    Ph.D.
    Computer Science
    2564
    University of Example / Vietnam
    """
    people = parse_curriculum_people(text)
    assert [item.person.fullName for item in people] == [
        "ผศ. ดร. สมชาย ใจดี",
        "Dr. Tran Anh Tuan",
    ]
    assert [len(item.educations) for item in people] == [2, 1]
    assert people[0].roles == ("programmeResponsible", "programmeStaff")
    assert people[1].roles == ()


def test_parse_cv_supports_multiple_education_and_academic_work_rows() -> None:
    result = parse_cv(
        """
        ชื่อ-นามสกุล: ผศ.ดร.สมชาย ใจดี

        ประวัติการศึกษา:
        degree | field | institution | graduationYear
        วท.ด. | วิทยาการคอมพิวเตอร์ | มหาวิทยาลัยตัวอย่าง | ๒๕๖๐
        วท.ม. | เทคโนโลยีสารสนเทศ | มหาวิทยาลัยทดสอบ | ๒๕๕๕

        ผลงานวิชาการ:
        workType | title | publicationYear | database | quartile
        Journal | Reliable Import Systems | ๒๕๖๗ | Scopus | q1
        Conference | Structured Parsing | ๒๕๖๖ | IEEE | -
        """
    )
    assert result.person.fullName == "ผศ. ดร. สมชาย ใจดี"
    assert [item.graduationYear for item in result.educations] == [2560, 2555]
    assert [item.title for item in result.academicWorks] == [
        "Reliable Import Systems",
        "Structured Parsing",
    ]
    assert result.academicWorks[0].quartile == "Q1"
    assert result.person.hasTeachingExperience is False


def test_parse_cv_detects_structured_teaching_experience() -> None:
    result = parse_cv(
        """
        Full Name: Dr. Teaching Evidence

        Education:
        Ph.D. | Computing | Test University | 2020

        Academic Works:
        Journal | Evidence Based Import | 2026 | Scopus | Q1

        Teaching Experience:
        courseName | institution | period
        Database Systems | Test University | 2021-2025
        """
    )

    assert result.person.hasTeachingExperience is True
    assert [work.title for work in result.academicWorks] == [
        "Evidence Based Import"
    ]


@pytest.mark.parametrize(
    "teaching_section",
    (
        "Teaching Experience: None",
        "Teaching Experience:\nไม่มีประสบการณ์สอน",
        "Teaching Experience: No teaching experience",
    ),
)
def test_parse_cv_records_false_when_teaching_experience_is_absent(
    teaching_section: str,
) -> None:
    result = parse_cv(
        f"""
        Full Name: Dr. No Teaching Evidence
        Education:
        Ph.D. | Computing | Test University | 2020
        Academic Works:
        Journal | Parsing | 2026 | Scopus | Q1
        {teaching_section}
        """
    )

    assert result.person.hasTeachingExperience is False


def test_parse_cv_preserves_docx_table_tab_delimiters() -> None:
    result = parse_cv(
        "\n".join(
            (
                "Full Name: Dr. Ada Lovelace",
                "Education:",
                "Ph.D.\tComputing\tUniversity of London\t1852",
                "Academic Works:",
                "Journal\tNotes on the Analytical Engine\t1843\tArchive\t-",
            )
        )
    )
    assert result.educations[0].institution == "University of London"
    assert result.academicWorks[0].publicationYear == 1843


def test_parse_cv_supports_numbered_thai_university_pdf_layout() -> None:
    result = parse_cv(
        """
        แบบฟอร์มประวัติและผลงานของอาจารย์ (Curriculum Vitae)
        ชื่อ-สกุล รองศาสตราจารย์ ดร.บูคอรี ซาเหาะ

        1. การศึกษา (เรียงลำดับจากปีล่าสุด)
        คุณวุฒิ
        สาขาวิชา/สถาบันการศึกษา
        ปี พ.ศ.
        ปร. ด.
        วิศวกรรมคอมพิวเตอร์ / มหาวิทยาลัยสงขลานครินทร์
        2563
        วท. ม.
        เทคโนโลยีสารสนเทศ / มหาวิทยาลัยทักษิณ
        2558

        2. ประสบการณ์การทำงาน (เรียงลำดับจากปีล่าสุด)
        ตำแหน่งงาน - องค์กรหรือหน่วยงาน

        4. ประสบการณ์การสอน (โดยเรียงจากปีล่าสุด)
         มี
         ไม่มี

        6. ผลงานทางวิชาการย้อนหลัง 5 ปี (ที่ไม่ใช่ส่วนหนึ่งของการศึกษาเพื่อรับปริญญา)
        6.1 บทความวิจัยที่ตีพิมพ์ในวารสารวิชาการระดับนานาชาติ
        ลำดับ
        ชื่อผลงานวิชาการ
        ฐานข้อมูล
        ปี
        เดือน
        1
        Author, A., & Sahoh, B. (2026). A sequential deep learning framework for
        proactive fault detection in Multi-Unit HVAC systems. Energy and Buildings, 117399.
        Scopus Q1
        2569
        มิถุนายน
        2
        Sahoh, B. (2025). Explainable systems for education. IEEE Access.
        Scopus Q1
        2568
        ธันวาคม

        7. เกียรติคุณและรางวัล
        """
    )

    assert result.person.fullName == "รศ. ดร. บูคอรี ซาเหาะ"
    assert result.person.hasTeachingExperience is True
    assert [education.graduationYear for education in result.educations] == [2563, 2558]
    assert result.educations[0].institution == "มหาวิทยาลัยสงขลานครินทร์"
    assert [work.publicationYear for work in result.academicWorks] == [2569, 2568]
    assert result.academicWorks[0].title == (
        "A sequential deep learning framework for proactive fault detection in Multi-Unit HVAC systems"
    )
    assert result.academicWorks[0].database == "Scopus"
    assert result.academicWorks[0].quartile == "Q1"


def test_parse_cv_supports_unlabeled_name_and_checo_work_table() -> None:
    result = parse_cv(
        """
        แบบฟอร์มประวัติและผลงานของอาจารย์ (Curriculum Vitae)
        ผู้ช่วยศาสตราจารย์ ดร.ชนันท์กรณ์ จันแดง (Assist. Dr. Chanankorn Jandaeng)

        1. การศึกษา (เรียงลำดับจากปีล่าสุด)
        ปร.ด.
        วิศวกรรมคอมพิวเตอร์ / มหาวิทยาลัยสงขลานครินทร์
        2555
        2. ประสบการณ์การทำงาน

        6. ผลงานทางวิชาการย้อนหลัง 5 ปี
        6.1 บทความวิจัย/บทความวิชาการ ที่ตีพิมพ์เผยแพร่ในวารสาร
        ลำดับ
        บทความวิจัย/บทความวิชาการ
        เกณฑ์มาตรฐาน (ระบุข้อ)
        ปี
        เดือน
        1
        Jandaeng, C. (2026). Reliable phishing email detection. Informatics, 13(5), 72.
        12
        2569 พฤษภาคม
        7. เกียรติคุณและรางวัล
        """
    )

    assert result.person.fullName == "ผศ. ดร. ชนันท์กรณ์ จันแดง"
    assert result.academicWorks[0].title == "Reliable phishing email detection"
    assert result.academicWorks[0].publicationYear == 2569
    assert result.academicWorks[0].database == ""
    assert result.academicWorks[0].quartile == ""


def test_parse_cv_supports_section_five_citation_lists_and_conferences() -> None:
    result = parse_cv(
        """
        Full Name: Dr. Nichnan Kittiphattanabawon
        1. การศึกษา
        Ph.D.
        Information Technology / Example University
        2560
        2. ประสบการณ์การทำงาน

        5. ผลงานทางวิชาการย้อนหลัง 5 ปี
        5.1 บทความวิจัย
        International Journal
        1) Author, A. (2024). A journal article title. Example Journal, 1(2), 3-4.
        5.2 บทความวิจัย/วิชาการที่เสนอในที่ประชุมวิชาการ
        Book Series
        1) Author, A. (2023). A conference paper title. In Example Conference.
        6. เกียรติคุณและรางวัล
        """
    )

    assert [work.workType for work in result.academicWorks] == ["Journal", "Conference"]
    assert [work.publicationYear for work in result.academicWorks] == [2024, 2023]


def test_parse_cv_splits_education_when_pdf_loses_table_column_boundary() -> None:
    result = parse_cv(
        """
        ชื่อ-สกุล ผู้ช่วยศาสตราจารย์ ดร.ธีรัช สายชู
        1. การศึกษา (เรียงลำดับจากปีล่าสุด)
        ปร.ด.
        การจัดการเทคโนโลยีสารสนเทศ มหาวิทยาลัยวลัยลักษณ์
        2565
        2. ประสบการณ์การทำงาน
        6. ผลงานทางวิชาการย้อนหลัง 5 ปี
        6.1 บทความวิจัย
        1
        Saichoo, T. (2026). Reliable software testing. Example Journal.
        12
        2569
        7. เกียรติคุณและรางวัล
        """
    )

    assert result.educations[0].field == "การจัดการเทคโนโลยีสารสนเทศ"
    assert result.educations[0].institution == "มหาวิทยาลัยวลัยลักษณ์"


def test_full_thai_lecturer_position_is_normalized() -> None:
    person = normalize_person_name("อาจารย์ ดร. สมใจ ทดสอบ")
    assert person.academicPosition == "อ."
    assert person.fullName == "อ. ดร. สมใจ ทดสอบ"


@pytest.mark.parametrize(
    ("raw", "expected"),
    (
        ("ผู้ช่วยศาสตราจารย์เจริญพร บัวแย้ม", "ผศ. เจริญพร บัวแย้ม"),
        ("รองศาสตาจารย์ ดร.ยรรยงค์ พันธ์สวัสดิ์", "รศ. ดร. ยรรยงค์ พันธ์สวัสดิ์"),
    ),
)
def test_official_order_position_text_is_normalized(
    raw: str,
    expected: str,
) -> None:
    assert normalize_person_name(raw).fullName == expected


def test_name_starting_with_thai_o_ang_is_not_treated_as_academic_position() -> None:
    person = normalize_person_name("อารี ใจดี")
    assert person.firstName == "อารี"
    assert person.academicPosition == ""


def test_parse_appointment_keeps_references_separate_for_phase_6_object_ids() -> None:
    result = parse_appointment(
        """
        ชื่อ-นามสกุล: ผศ. ดร สมชาย ใจดี
        รหัสหลักสูตร: CS-001
        บทบาท: อาจารย์ผู้รับผิดชอบหลักสูตร
        ชื่อบทบาท: ประธานหลักสูตร
        วันที่มีผล: 1 มกราคม 2567
        เลขที่คำสั่ง: 123/2567
        วันที่คำสั่ง: 15 ธันวาคม 2566
        สถานะ: ACTIVE
        """
    )
    assert result.appointment.model_dump() == {
        "role": "programmeResponsible",
        "roleName": "ประธานหลักสูตร",
        "effectiveDate": "1 มกราคม 2567",
        "appointmentOrder": {
            "orderNumber": "123/2567",
            "orderDate": "15 ธันวาคม 2566",
        },
        "status": "active",
    }
    assert result.personReference.fullName == "ผศ. ดร. สมชาย ใจดี"
    assert result.curriculumReference.curriculumCode == "CS-001"


def test_parse_multi_person_thai_appointment_order() -> None:
    results = parse_appointments(
        """
        คำสั่งมหาวิทยาลัยวลัยลักษณ์
        ที่  ๓๕๐/๒๕๖๘
        เรื่อง แต่งตั้งอาจารย์ผู้รับผิดชอบหลักสูตรและอาจารย์ประจำหลักสูตร

        อาจารย์ผู้รับผิดชอบหลักสูตร
        ๑. ผู้ช่วยศาสตราจารย์ ดร.พีรวิชญ์ เควด
        ๒. อาจารย์จงสุข คงเสน

        อาจารย์ประจำหลักสูตร
        ๑. ผู้ช่วยศาสตราจารย์กาญจนา หฤหรรษพงศ์
        ๒. อาจารย์ ดร.ชนันท์กรณ์ จันแดง
        ๓. รองศาสตราจารย์ ดร.ยรรยงค์ พันธ์สวัสดิ์

        ทั้งนี้ ตั้งแต่ วันที่ ๑๓ พฤศจิกายน พ.ศ. ๒๕๖๗ เป็นต้นไป
        สั่ง ณ วันที่ ๔ กุมภาพันธ์ พ.ศ. ๒๕๖๘
        """,
        curriculum_code="25500231104894",
    )

    assert len(results) == 5
    assert [item.appointment.role for item in results] == [
        "programmeResponsible",
        "programmeResponsible",
        "programmeStaff",
        "programmeStaff",
        "programmeStaff",
    ]
    assert results[0].appointment.appointmentOrder.orderNumber == "350/2568"
    assert results[0].appointment.appointmentOrder.orderDate == (
        "4 กุมภาพันธ์ พ.ศ. 2568"
    )
    assert results[0].appointment.effectiveDate == "13 พฤศจิกายน พ.ศ. 2567"
    assert results[0].appointment.status == "active"
    assert results[1].personReference.fullName == "อ. จงสุข คงเสน"
    assert results[2].personReference.fullName == "ผศ. กาญจนา หฤหรรษพงศ์"
    assert results[0].curriculumReference.curriculumCode == "25500231104894"


def test_required_curriculum_field_is_rejected() -> None:
    with pytest.raises(StructuredParsingError, match="curriculumName"):
        parse_curriculum(
            """
            curriculumCode: CS-001
            curriculumYear: 2024
            version: 1
            status: active
            """
        )
