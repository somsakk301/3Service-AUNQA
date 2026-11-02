import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from app.api.routes import auth, monitor
from app.error_log import SYSTEM_ERROR, configure_logging, log_error
from app.settings import Settings

_log = logging.getLogger(__name__)


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title="Mornitor", description="Read-only monitoring API", version="0.4.0")

    @app.middleware("http")
    async def log_unexpected_errors(request: Request, call_next):
        """An exception no route handles: logged as a System Error (traceback) and answered exactly as before,
        500 "Internal Server Error" (plain text), so no traceback reaches the client. Only method and path are
        logged: no query, body, header or cookie."""
        try:
            return await call_next(request)
        except Exception as exc:
            log_error(_log, SYSTEM_ERROR, "Unexpected error in %s %s", request.method, request.url.path, exc_info=exc)
            return PlainTextResponse("Internal Server Error", status_code=500)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(Settings.from_env().cors_origins),
        allow_methods=["GET", "POST"],   # POST: the Monitor-owned write routes, plus login/logout
        allow_headers=["*"],
    )
    app.include_router(monitor.router)
    app.include_router(auth.router)
    @app.get("/health", include_in_schema=False)
    def health():
        from pymongo import MongoClient
        from fastapi import HTTPException
        try:
            with MongoClient(Settings.from_env().source_db_uri, serverSelectionTimeoutMS=3000) as client:
                client.admin.command("ping")
        except Exception:
            raise HTTPException(status_code=503, detail="Database unavailable") from None
        return {"status": "ok"}
    return app


app = create_app()
