"""Response schemas for document intake."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel


class LocalFileReference(BaseModel):
    storage: Literal["local"]
    path: str


class DocumentUploadResponse(BaseModel):
    documentId: str
    documentType: Literal["curriculum", "cv", "appointment"]
    fileType: Literal["pdf", "doc", "docx"]
    fileName: str
    curriculumId: str
    originalFile: LocalFileReference
    status: Literal["uploaded"]
    timestamp: datetime


class DocumentProcessingResponse(BaseModel):
    documentId: str
    status: Literal["processed"]
    structuredRecords: dict[str, list[str]]
    chunkCount: int


class ImportPreviewResponse(BaseModel):
    previewId: str
    documentType: Literal["curriculum", "cv", "appointment"]
    fileType: Literal["pdf", "doc", "docx"]
    fileName: str
    curriculumId: str
    collections: dict[str, list[dict[str, Any]]]
    systemPreview: dict[str, list[dict[str, Any]]]
    chunks: list[dict[str, Any]]


class CurriculumOption(BaseModel):
    curriculumId: str
    curriculumCode: str
    curriculumName: str
    curriculumYear: int
    version: int


class PersonOption(BaseModel):
    personId: str
    fullName: str


class TemplateUploadResponse(BaseModel):
    templateId: str
    version: int
    fileName: str
    fileType: Literal["docx", "pdf"]
    originalFile: LocalFileReference
    timestamp: datetime
