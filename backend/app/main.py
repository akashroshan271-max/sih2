"""FastAPI application entrypoint.

Run locally:  uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.api.deps import DbSession, get_current_officer
from app.api.v1 import auth
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.services.errors import DomainError

settings = get_settings()

app = FastAPI(
    title=f"{settings.project_name} API",
    version=settings.version,
    summary="Verification flow for AICTE approvals under APH 2024-27",
    description=(
        "Statutory approval workflow automation for AICTE institutions under "
        "APH 2024-27: live-lease compliance (Rule 1), multi-stage triage "
        "(Rule 2), SLA dwell-time escalation (Rule 3) and a SHA-256 chained "
        "audit trail."
    ),
    openapi_url=f"{settings.api_v1_prefix}/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-Id"],
)


@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    """Map business failures to their documented HTTP status (never a 500)."""
    return JSONResponse(status_code=exc.http_status, content=exc.as_dict())


@app.get("/health", tags=["system"])
def health(db: DbSession) -> dict[str, str]:
    database_up = True
    try:
        db.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001 - health must report, never raise
        database_up = False
    return {
        "status": "ok" if database_up else "degraded",
        "service": settings.project_name,
        "version": settings.version,
        "environment": settings.environment,
        "database": "up" if database_up else "down",
    }


@app.get("/", tags=["system"])
def root() -> dict[str, str]:
    return {
        "service": settings.project_name,
        "docs": "/docs",
        "openapi": f"{settings.api_v1_prefix}/openapi.json",
        "health": "/health",
    }


# Sign-in itself must stay open; every other v1 route requires a valid officer
# session. The desk-level permission checks live in the individual routers.
app.include_router(auth.router, prefix=settings.api_v1_prefix)
app.include_router(
    api_router,
    prefix=settings.api_v1_prefix,
    dependencies=[Depends(get_current_officer)],
)

# Local document storage doubles as the demo media origin (S3 in production).
if settings.storage_backend == "local":
    upload_dir = settings.resolved_upload_dir()
    upload_dir.mkdir(parents=True, exist_ok=True)
    app.mount(
        settings.media_url_prefix,
        StaticFiles(directory=upload_dir),
        name="media",
    )
