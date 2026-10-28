"""Audit trail verification endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select

from app.api.deps import (
    CurrentActor,
    DbSession,
    load_application,
    require_roles,
)
from app.models import AuditLog, OfficerRole
from app.schemas.audit import (
    AuditListResponse,
    AuditLogRead,
    ChainVerificationRead,
    ChainVerificationResponse,
)
from app.services.audit import AuditService
from app.services.permissions import ensure_can_view

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/applications/{application_id}/verify", response_model=ChainVerificationResponse)
def verify_chain(
    application_id: uuid.UUID,
    db: DbSession,
    actor: CurrentActor,
) -> ChainVerificationResponse:
    """Recompute the SHA-256 chain for one docket (tamper evidence)."""
    application = load_application(db, application_id)
    ensure_can_view(actor.role_enum, application)
    verification = AuditService(db).verify(application_id)
    return ChainVerificationResponse(
        application_id=application.id,
        application_number=application.application_number,
        verification=ChainVerificationRead.model_validate(verification),
    )


@router.get(
    "/logs",
    response_model=AuditListResponse,
    dependencies=[Depends(require_roles(OfficerRole.REGIONAL_OFFICER))],
)
def recent_logs(
    db: DbSession,
    application_id: Annotated[uuid.UUID | None, Query()] = None,
    action: Annotated[str | None, Query(max_length=64)] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AuditListResponse:
    conditions = []
    if application_id is not None:
        conditions.append(AuditLog.application_id == application_id)
    if action is not None:
        conditions.append(AuditLog.action == action)

    total = int(
        db.execute(
            select(func.count()).select_from(AuditLog).where(*conditions)
        ).scalar_one()
    )
    stmt = (
        select(AuditLog)
        .where(*conditions)
        .order_by(AuditLog.timestamp.desc(), AuditLog.id.desc())
        .limit(limit)
        .offset(offset)
    )
    entries = list(db.execute(stmt).scalars().all())
    return AuditListResponse(
        items=[AuditLogRead.model_validate(entry) for entry in entries],
        total=total,
    )
