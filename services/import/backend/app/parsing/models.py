"""Phase 5 parser models using the locked SRS field names."""

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CurriculumData(StrictModel):
    curriculumCode: str = Field(min_length=1)
    curriculumName: str = Field(min_length=1)
    curriculumYear: int
    version: int
    status: str = Field(min_length=1)


class PersonData(StrictModel):
    title: str
    firstName: str = Field(min_length=1)
    lastName: str = Field(min_length=1)
    fullName: str = Field(min_length=1)
    academicPosition: str
    hasTeachingExperience: bool | None = None


class EducationData(StrictModel):
    degree: str = Field(min_length=1)
    field: str = Field(min_length=1)
    institution: str = Field(min_length=1)
    graduationYear: int


class AcademicWorkData(StrictModel):
    workType: str = Field(min_length=1)
    title: str = Field(min_length=1)
    publicationYear: int
    database: str
    quartile: str


class CVParseResult(StrictModel):
    person: PersonData
    educations: list[EducationData]
    academicWorks: list[AcademicWorkData]


class AppointmentOrderData(StrictModel):
    orderNumber: str = Field(min_length=1)
    orderDate: str = Field(min_length=1)


class AppointmentData(StrictModel):
    role: str = Field(pattern="^(programmeResponsible|programmeStaff)$")
    roleName: str = Field(min_length=1)
    effectiveDate: str = Field(min_length=1)
    appointmentOrder: AppointmentOrderData
    status: str = Field(min_length=1)


class PersonReference(StrictModel):
    fullName: str = Field(min_length=1)


class CurriculumReference(StrictModel):
    curriculumCode: str = Field(min_length=1)


class AppointmentParseResult(StrictModel):
    appointment: AppointmentData
    personReference: PersonReference
    curriculumReference: CurriculumReference
