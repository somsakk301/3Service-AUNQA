"""HTTP endpoints for document intake and SRS import-pipeline processing."""

import asyncio
import json
import logging
from typing import Annotated

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import ValidationError

from app.config import get_settings
from app.connections import ServiceConnections
from app.pipeline import ImportPipeline, ImportPipelineError
from app.schemas.document import (
    CurriculumOption,
    DocumentProcessingResponse,
    DocumentUploadResponse,
    ImportPreviewResponse,
    PersonOption,
    TemplateUploadResponse,
)
from app.services.document_import import (
    CurriculumReferenceError,
    DocumentFileNotFoundError,
    DocumentImportService,
)
from app.services.file_validation import DocumentValidationError, validate_upload
from app.services.import_preview import ImportPreviewError, ImportPreviewService
from app.services.template_import import (
    TemplateImportService,
    TemplateNotFoundError,
    TemplateValidationError,
    TemplateVersionConflictError,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["Import"])


@router.get("/documents/{document_id}/file", response_class=FileResponse)
async def view_original_document(request: Request, document_id: str) -> FileResponse:
    """Open the original file for a MongoDB documents record in the browser."""

    connections: ServiceConnections = request.app.state.connections
    service = DocumentImportService(get_settings(), connections.mongodb_database)
    try:
        path, file_name = await asyncio.to_thread(service.get_original_file, document_id)
    except DocumentFileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return FileResponse(
        path,
        filename=file_name,
        content_disposition_type="inline",
    )


@router.post("/import/preview", response_model=ImportPreviewResponse)
async def preview_document(
    request: Request,
    document_type: Annotated[str, Form(alias="documentType")],
    file: Annotated[UploadFile, File()],
    curriculum_id: Annotated[str | None, Form(alias="curriculumId")] = None,
    curriculum_version: Annotated[int | None, Form(alias="curriculumVersion")] = None,
    curriculum_status: Annotated[str | None, Form(alias="curriculumStatus")] = None,
) -> ImportPreviewResponse:
    """Extract and parse one file without writing MongoDB or ChromaDB."""

    try:
        content = await file.read()
        upload = await asyncio.to_thread(
            validate_upload,
            document_type=document_type,
            file_name=file.filename,
            content_type=file.content_type,
            content=content,
        )
        connections: ServiceConnections = request.app.state.connections
        service = ImportPreviewService(
            settings=get_settings(),
            database=connections.mongodb_database,
        )
        result = await asyncio.to_thread(
            service.preview,
            upload=upload,
            curriculum_id=curriculum_id,
            curriculum_version=curriculum_version,
            curriculum_status=curriculum_status,
        )
        logger.info(
            "Import Preview completed previewId=%s fileName=%s",
            result["previewId"],
            upload.file_name,
        )
        return ImportPreviewResponse.model_validate(result)
    except (
        DocumentValidationError,
        ImportPreviewError,
        ValidationError,
        ValueError,
    ) as exc:
        logger.warning("Import Preview validation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Import Preview failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Import Preview failed",
        ) from exc
    finally:
        await file.close()


@router.post(
    "/import/confirm",
    response_model=DocumentProcessingResponse,
    status_code=status.HTTP_201_CREATED,
)
async def confirm_document(
    request: Request,
    document_type: Annotated[str, Form(alias="documentType")],
    curriculum_id: Annotated[str, Form(alias="curriculumId")],
    preview_data: Annotated[str, Form(alias="previewData")],
    file: Annotated[UploadFile, File()],
) -> DocumentProcessingResponse:
    """Validate edited Preview data, then perform the persistent import."""

    try:
        content = await file.read()
        upload = await asyncio.to_thread(
            validate_upload,
            document_type=document_type,
            file_name=file.filename,
            content_type=file.content_type,
            content=content,
        )
        try:
            payload = json.loads(preview_data)
        except json.JSONDecodeError as exc:
            raise ImportPreviewError("previewData must be valid JSON") from exc
        if not isinstance(payload, dict):
            raise ImportPreviewError("previewData must be a JSON object")
        if (
            payload.get("documentType") != upload.document_type
            or payload.get("fileType") != upload.extension.removeprefix(".")
            or payload.get("fileName") != upload.file_name
            or payload.get("curriculumId") != curriculum_id
        ):
            raise ImportPreviewError(
                "Preview identity does not match the confirmed file"
            )
        try:
            preview_id = ObjectId(payload.get("previewId"))
        except (InvalidId, TypeError) as exc:
            raise ImportPreviewError("previewId must be a valid ObjectId") from exc

        connections: ServiceConnections = request.app.state.connections
        preview_service = ImportPreviewService(
            settings=get_settings(),
            database=connections.mongodb_database,
        )
        await asyncio.to_thread(
            preview_service.validate_confirmation,
            upload=upload,
            curriculum_id=curriculum_id,
            payload=payload,
        )
        import_service = DocumentImportService(
            settings=get_settings(),
            database=connections.mongodb_database,
        )
        upload_result = await asyncio.to_thread(
            import_service.import_document,
            upload=upload,
            curriculum_id=curriculum_id,
            document_id=preview_id,
        )
        pipeline: ImportPipeline = request.app.state.import_pipeline
        result = await asyncio.to_thread(
            pipeline.process,
            upload_result["documentId"],
            preview_data=payload,
        )
        return DocumentProcessingResponse.model_validate(result.to_dict())
    except (
        DocumentValidationError,
        CurriculumReferenceError,
        ImportPreviewError,
        ValidationError,
        ValueError,
    ) as exc:
        logger.warning("Import confirmation validation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except ImportPipelineError as exc:
        logger.warning("Confirmed Import pipeline failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Confirmed Import failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Confirmed Import failed",
        ) from exc
    finally:
        await file.close()


@router.get("/curricula", response_model=list[CurriculumOption])
async def list_curricula(request: Request) -> list[CurriculumOption]:
    """Return existing curricula for the SRS-required curriculum selector."""

    connections: ServiceConnections = request.app.state.connections

    def read_curricula() -> list[CurriculumOption]:
        cursor = connections.mongodb_database["curricula"].find(
            {},
            {
                "curriculumCode": 1,
                "curriculumName": 1,
                "curriculumYear": 1,
                "version": 1,
            },
        ).sort(
            [
                ("curriculumCode", 1),
                ("curriculumYear", -1),
                ("version", -1),
            ]
        )
        return [
            CurriculumOption(
                curriculumId=str(item["_id"]),
                curriculumCode=item["curriculumCode"],
                curriculumName=item["curriculumName"],
                curriculumYear=item["curriculumYear"],
                version=item["version"],
            )
            for item in cursor
        ]

    return await asyncio.to_thread(read_curricula)


@router.get("/persons", response_model=list[PersonOption])
async def list_persons(request: Request) -> list[PersonOption]:
    """Return existing people as user-facing choices for Import forms."""

    connections: ServiceConnections = request.app.state.connections

    def read_persons() -> list[PersonOption]:
        cursor = connections.mongodb_database["persons"].find(
            {}, {"fullName": 1}
        ).sort("fullName", 1)
        return [
            PersonOption(personId=str(item["_id"]), fullName=item["fullName"])
            for item in cursor
        ]

    return await asyncio.to_thread(read_persons)


@router.post(
    "/templates",
    response_model=TemplateUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def import_template(
    request: Request,
    version: Annotated[int, Form()],
    file: Annotated[UploadFile, File()],
) -> TemplateUploadResponse:
    """Store one versioned DOCX template without running the document pipeline."""

    logger.info("Template upload received version=%s fileName=%s", version, file.filename)
    try:
        content = await file.read()
        connections: ServiceConnections = request.app.state.connections
        service = TemplateImportService(
            settings=get_settings(),
            database=connections.mongodb_database,
        )
        result = await asyncio.to_thread(
            service.import_template,
            version=version,
            file_name=file.filename,
            content=content,
        )
        return TemplateUploadResponse.model_validate(result)
    except TemplateVersionConflictError as exc:
        logger.warning("Template version conflict: %s", exc)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except TemplateValidationError as exc:
        logger.warning("Template validation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Template upload failed due to an internal error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Template upload failed",
        ) from exc
    finally:
        await file.close()


@router.get("/templates/{version}/download", response_class=FileResponse)
async def download_template(request: Request, version: int) -> FileResponse:
    """Download a stored PS template by its unique positive version."""

    connections: ServiceConnections = request.app.state.connections
    service = TemplateImportService(
        settings=get_settings(),
        database=connections.mongodb_database,
    )
    try:
        path, file_name = await asyncio.to_thread(service.get_template_file, version)
    except TemplateNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    logger.info("Template download version=%s fileName=%s", version, file_name)
    return FileResponse(
        path,
        media_type=(
            "application/pdf"
            if path.suffix.lower() == ".pdf"
            else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
        filename=file_name,
    )


@router.post(
    "/import",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def import_document(
    request: Request,
    document_type: Annotated[str, Form(alias="documentType")],
    curriculum_id: Annotated[str, Form(alias="curriculumId")],
    file: Annotated[UploadFile, File()],
) -> DocumentUploadResponse:
    """Validate and persist an original document, then create documents record."""

    logger.info(
        "Upload received documentType=%s fileName=%s",
        document_type,
        file.filename,
    )
    try:
        content = await file.read()
        validated_upload = await asyncio.to_thread(
            validate_upload,
            document_type=document_type,
            file_name=file.filename,
            content_type=file.content_type,
            content=content,
        )
        logger.info(
            "Validation completed documentType=%s fileName=%s",
            validated_upload.document_type,
            validated_upload.file_name,
        )

        connections: ServiceConnections = request.app.state.connections
        service = DocumentImportService(
            settings=get_settings(),
            database=connections.mongodb_database,
        )
        result = await asyncio.to_thread(
            service.import_document,
            upload=validated_upload,
            curriculum_id=curriculum_id,
        )
        return DocumentUploadResponse.model_validate(result)
    except (DocumentValidationError, CurriculumReferenceError) as exc:
        logger.warning("Import validation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Import failed due to an internal error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Import failed",
        ) from exc
    finally:
        await file.close()


@router.post(
    "/import/{document_id}/process",
    response_model=DocumentProcessingResponse,
)
async def process_import(
    request: Request,
    document_id: str,
) -> DocumentProcessingResponse:
    """Run SRS steps 05-20 for an uploaded or failed document."""

    pipeline: ImportPipeline = request.app.state.import_pipeline
    try:
        result = await asyncio.to_thread(pipeline.process, document_id)
        return DocumentProcessingResponse.model_validate(result.to_dict())
    except ImportPipelineError as exc:
        logger.warning("Import pipeline rejected documentId=%s: %s", document_id, exc)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Import pipeline failed documentId=%s", document_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Import processing failed",
        ) from exc
