"""API v1 router aggregation."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    applications,
    audit,
    dashboard,
    documents,
    institutions,
    workspace,
)

api_router = APIRouter()
api_router.include_router(workspace.router)
api_router.include_router(institutions.router)
api_router.include_router(applications.router)
api_router.include_router(documents.router)
api_router.include_router(dashboard.router)
api_router.include_router(audit.router)
