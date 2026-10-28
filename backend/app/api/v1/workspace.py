"""The signed-in officer's own desk."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentOfficer, DbSession
from app.schemas.workspace import WorkspaceResponse
from app.services.workspace import WorkspaceService

router = APIRouter(prefix="/workspace", tags=["workspace"])


@router.get("", response_model=WorkspaceResponse)
def get_workspace(officer: CurrentOfficer, db: DbSession) -> WorkspaceResponse:
    """Dockets at this officer's stage, with the facts and moves they need."""
    return WorkspaceService(db).build(officer)
