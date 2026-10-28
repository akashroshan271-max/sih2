"""Institution registry endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from app.api.deps import DbSession, require_roles
from app.models import Institution, InstitutionType, OfficerRole
from app.schemas.institution import (
    InstitutionCreate,
    InstitutionListResponse,
    InstitutionRead,
)
from app.services.errors import ConflictError, NotFoundError

router = APIRouter(prefix="/institutions", tags=["institutions"])


@router.get("", response_model=InstitutionListResponse)
def list_institutions(
    db: DbSession,
    q: Annotated[str | None, Query(max_length=120)] = None,
    state: Annotated[str | None, Query(max_length=64)] = None,
    institution_type: Annotated[InstitutionType | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> InstitutionListResponse:
    conditions = []
    if q:
        like = f"%{q.strip()}%"
        conditions.append(
            or_(
                Institution.name.ilike(like),
                Institution.aicte_permanent_id.ilike(like),
            )
        )
    if state:
        conditions.append(Institution.state == state)
    if institution_type is not None:
        conditions.append(Institution.institution_type == institution_type)

    total = int(
        db.execute(
            select(func.count()).select_from(Institution).where(*conditions)
        ).scalar_one()
    )
    stmt = (
        select(Institution)
        .where(*conditions)
        .order_by(Institution.name.asc())
        .limit(limit)
        .offset(offset)
    )
    institutions = list(db.execute(stmt).scalars().all())
    return InstitutionListResponse(
        items=[InstitutionRead.model_validate(item) for item in institutions],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=InstitutionRead,
    dependencies=[Depends(require_roles(OfficerRole.REGIONAL_OFFICER))],
)
def create_institution(payload: InstitutionCreate, db: DbSession) -> InstitutionRead:
    institution = Institution(**payload.model_dump())
    db.add(institution)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(
            f"AICTE Permanent ID {payload.aicte_permanent_id} is already registered.",
            context={"aicte_permanent_id": payload.aicte_permanent_id},
        ) from exc
    db.refresh(institution)
    return InstitutionRead.model_validate(institution)


@router.get("/{institution_id}", response_model=InstitutionRead)
def get_institution(institution_id: uuid.UUID, db: DbSession) -> InstitutionRead:
    institution = db.get(Institution, institution_id)
    if institution is None:
        raise NotFoundError(f"Institution {institution_id} was not found.")
    return InstitutionRead.model_validate(institution)
