"""FastAPI application for the SRS-defined Import Service."""

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.connections import ServiceConnections
from app.database.bootstrap import ensure_database_schema
from app.logging_config import configure_logging
from app.pipeline import ImportPipeline
from app.routers.imports import router as import_router

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)
static_root = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Verify required services before accepting traffic."""

    connections = ServiceConnections(settings)
    try:
        await asyncio.to_thread(connections.check_all)
        await asyncio.to_thread(
            ensure_database_schema,
            connections.mongodb_database,
        )
        application.state.connections = connections
        application.state.import_pipeline = ImportPipeline(
            settings,
            connections.mongodb_database,
        )
        logger.info("Import Service infrastructure is ready", extra={"event": "startup"})
        yield
    finally:
        connections.close()


app = FastAPI(
    title="AUN-QA Import Service",
    version="1.0.0",
    lifespan=lifespan,
)
app.include_router(import_router)
app.mount("/static", StaticFiles(directory=static_root), name="static")


@app.get("/", include_in_schema=False, response_class=FileResponse)
async def import_page() -> FileResponse:
    """Serve the single SRS-defined Import Document page."""

    return FileResponse(static_root / "index.html")


@app.get("/health", include_in_schema=False)
async def health(request: Request) -> dict[str, object]:
    """Report live MongoDB and ChromaDB connectivity."""

    try:
        connections: ServiceConnections = request.app.state.connections
        services = await asyncio.to_thread(connections.check_all)
    except Exception as exc:
        logger.exception("Health check failed", extra={"event": "error"})
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Required data service is unavailable",
        ) from exc
    return {"status": "ok", "services": services}
