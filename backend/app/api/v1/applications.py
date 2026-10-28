"""Application docket endpoints: intake, triage, documents and detail views."""

from __future__ import annotations

import re
import uuid
from datetime import timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, File, Form, Query, UploadFile, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.deps import Actor, CurrentActor, DbSession, load_application
from app.core.config import get_settings
from app.core.time import utcnow
from app.models import (
    ACTIVE_STAGES,
    Application,
    ApplicationStatus,
    ApplicationType,
    Document,
    DocumentType,
    Institution,
    OfficerRole,
    ProgrammeLevel,
)
from app.schemas.application import (
    ApplicationCreate,
    ApplicationDetail,
    ApplicationListResponse,
    ApplicationRead,
    LeaseVerdictRead,
    TransitionRequest,
    TransitionResponse,
)
from app.schemas.audit import AuditLogRead
from app.schemas.document import DocumentRead
from app.services.audit import AuditService
from app.services.compliance import evaluate_live_lease
from app.services.errors import ConflictError, ValidationFailure
from app.services.permissions import (
    ensure_can_create_application,
    ensure_can_transition,
    ensure_can_upload,
    ensure_can_view,
    permitted_transitions,
    stage_for_role,
)
from app.services.storage import StorageService
from app.services.workflow import WorkflowService

router = APIRouter(prefix="/applications", tags=["applications"])

#: Statutory maximum course duration by programme level (years).
DEFAULT_MAX_DURATION: dict[ProgrammeLevel, float] = {
    ProgrammeLevel.DIPLOMA: 3.0,
    ProgrammeLevel.UG: 4.0,
    ProgrammeLevel.PG: 2.0,
    ProgrammeLevel.INTEGRATED: 5.0,
}


# =============================================================================
# Helpers
# =============================================================================


def build_detail(
    db: Session, application: Application, actor: Actor
) -> ApplicationDetail:
    """Full docket view: documents, lease verdict, this desk's moves, audit trail."""
    detail = ApplicationDetail.model_validate(application)
    detail.lease_verdict = LeaseVerdictRead.model_validate(
        evaluate_live_lease(db, application)
    )
    detail.allowed_transitions = list(
        permitted_transitions(actor.role_enum, application)
    )
    detail.audit_trail = [
        AuditLogRead.model_validate(entry)
        for entry in AuditService(db).timeline(application.id, limit=100)
    ]
    return detail


def _docket_number(db: Session, institution: Institution, academic_year: str) -> str:
    state_code = re.sub(r"[^A-Z]", "", institution.state.upper())[:2] or "IN"
    sequence = db.execute(
        select(func.count())
        .select_from(Application)
        .where(Application.academic_year == academic_year)
    ).scalar_one()
    return f"AICTE/{state_code}/{academic_year}/{sequence + 1:06d}"


def _apply_filters(
    stmt,
    *,
    app_status: ApplicationStatus | None,
    application_type: ApplicationType | None,
    programme_level: ProgrammeLevel | None,
    academic_year: str | None,
    state: str | None,
    institution_id: uuid.UUID | None,
    sla_breached: bool | None,
    q: str | None,
):
    if app_status is not None:
        stmt = stmt.where(Application.status == app_status)
    if application_type is not None:
        stmt = stmt.where(Application.application_type == application_type)
    if programme_level is not None:
        stmt = stmt.where(Application.programme_level == programme_level)
    if academic_year is not None:
        stmt = stmt.where(Application.academic_year == academic_year)
    if state is not None:
        stmt = stmt.where(Institution.state == state)
    if institution_id is not None:
        stmt = stmt.where(Application.institution_id == institution_id)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(Application.application_number.ilike(like), Institution.name.ilike(like))
        )
    if sla_breached is not None:
        cutoff = utcnow() - timedelta(days=get_settings().sla_threshold_days)
        overdue = (Application.status.in_(tuple(ACTIVE_STAGES))) & (
            Application.stage_entry_timestamp < cutoff
        )
        stmt = stmt.where(overdue if sla_breached else ~overdue)
    return stmt


# =============================================================================
# Collection
# =============================================================================


@router.get("", response_model=ApplicationListResponse)
def list_applications(
    db: DbSession,
    actor: CurrentActor,
    status_filter: Annotated[ApplicationStatus | None, Query(alias="status")] = None,
    application_type: Annotated[ApplicationType | None, Query()] = None,
    programme_level: Annotated[ProgrammeLevel | None, Query()] = None,
    academic_year: Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}$")] = None,
    state: Annotated[str | None, Query(max_length=64)] = None,
    institution_id: Annotated[uuid.UUID | None, Query()] = None,
    sla_breached: Annotated[bool | None, Query()] = None,
    q: Annotated[str | None, Query(max_length=120)] = None,
    sort: Annotated[
        Literal["stage_entry_asc", "stage_entry_desc", "created_desc"],
        Query(),
    ] = "stage_entry_asc",
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ApplicationListResponse:
    # Desk custody: a stage officer can only ever list their own stage, whatever
    # filter they ask for. The Regional Officer sees every stage.
    desk_stage = stage_for_role(OfficerRole(actor.role))
    effective_status = desk_stage if desk_stage is not None else status_filter

    base = select(Application).join(
        Institution, Institution.id == Application.institution_id
    )
    base = _apply_filters(
        base,
        app_status=effective_status,
        application_type=application_type,
        programme_level=programme_level,
        academic_year=academic_year,
        state=state,
        institution_id=institution_id,
        sla_breached=sla_breached,
        q=q,
    )

    count_stmt = select(func.count()).select_from(Application).join(
        Institution, Institution.id == Application.institution_id
    )
    count_stmt = _apply_filters(
        count_stmt,
        app_status=effective_status,
        application_type=application_type,
        programme_level=programme_level,
        academic_year=academic_year,
        state=state,
        institution_id=institution_id,
        sla_breached=sla_breached,
        q=q,
    )
    total = int(db.execute(count_stmt).scalar_one())

    order = {
        "stage_entry_asc": Application.stage_entry_timestamp.asc(),
        "stage_entry_desc": Application.stage_entry_timestamp.desc(),
        "created_desc": Application.created_at.desc(),
    }[sort]

    stmt = (
        base.options(selectinload(Application.institution))
        .order_by(order)
        .limit(limit)
        .offset(offset)
    )
    applications = list(db.execute(stmt).scalars().all())

    return ApplicationListResponse(
        items=[ApplicationRead.model_validate(application) for application in applications],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ApplicationDetail)
def create_application(
    payload: ApplicationCreate,
    db: DbSession,
    actor: CurrentActor,
) -> ApplicationDetail:
    ensure_can_create_application(actor.role_enum)

    institution = db.get(Institution, payload.institution_id)
    if institution is None:
        raise ConflictError(
            f"Institution {payload.institution_id} does not exist.",
            context={"institution_id": str(payload.institution_id)},
        )

    duplicate = db.execute(
        select(Application.id).where(
            Application.institution_id == payload.institution_id,
            Application.academic_year == payload.academic_year,
            Application.application_type == payload.application_type,
            Application.programme_level == payload.programme_level,
        )
    ).scalar_one_or_none()
    if duplicate is not None:
        raise ConflictError(
            f"A {payload.application_type.value} {payload.programme_level.value} "
            f"application for {payload.academic_year} already exists for this "
            "institution.",
            context={"application_id": str(duplicate)},
        )

    duration = payload.max_course_duration_years or DEFAULT_MAX_DURATION[
        payload.programme_level
    ]

    application: Application | None = None
    for _attempt in range(2):
        application = Application(
            application_number=_docket_number(db, institution, payload.academic_year),
            institution_id=payload.institution_id,
            academic_year=payload.academic_year,
            application_type=payload.application_type,
            programme_level=payload.programme_level,
            max_course_duration_years=duration,
            status=ApplicationStatus.SCRUTINY,
            stage_entry_timestamp=utcnow(),
            submitted_at=utcnow() if payload.submitted else None,
            proposed_intake=payload.proposed_intake,
        )
        db.add(application)
        try:
            db.commit()
            break
        except IntegrityError:
            db.rollback()
            application = None
    if application is None:
        raise ConflictError("Could not allocate a unique docket number; please retry.")

    db.refresh(application)
    AuditService(db).record(
        application=application,
        action="application.created",
        actor=actor.id,
        actor_role=actor.role,
        to_status=ApplicationStatus.SCRUTINY,
        payload={
            "application_type": payload.application_type.value,
            "programme_level": payload.programme_level.value,
            "academic_year": payload.academic_year,
            "max_course_duration_years": duration,
            "proposed_intake": payload.proposed_intake,
            "institution_id": str(institution.id),
        },
        commit=True,
    )
    return build_detail(db, application, actor)


# =============================================================================
# Single docket
# =============================================================================


@router.get("/{application_id}", response_model=ApplicationDetail)
def get_application(
    application_id: uuid.UUID, db: DbSession, actor: CurrentActor
) -> ApplicationDetail:
    application = load_application(db, application_id)
    ensure_can_view(actor.role_enum, application)
    return build_detail(db, application, actor)


@router.get("/{application_id}/lease-verdict", response_model=LeaseVerdictRead)
def get_lease_verdict(
    application_id: uuid.UUID, db: DbSession, actor: CurrentActor
) -> LeaseVerdictRead:
    application = load_application(db, application_id)
    ensure_can_view(actor.role_enum, application)
    return LeaseVerdictRead.model_validate(evaluate_live_lease(db, application))


@router.post("/{application_id}/transition", response_model=TransitionResponse)
def transition_application(
    application_id: uuid.UUID,
    payload: TransitionRequest,
    db: DbSession,
    actor: CurrentActor,
) -> TransitionResponse:
    application = load_application(db, application_id)
    ensure_can_transition(actor.role_enum, application, payload.to_status)
    result = WorkflowService(db).transition(
        application,
        payload.to_status,
        actor=actor.id,
        actor_role=actor.role,
        remarks=payload.remarks,
    )
    return TransitionResponse(
        application=build_detail(db, result.application, actor),
        audit_log=AuditLogRead.model_validate(result.audit_log),
        from_status=result.from_status,
        to_status=result.to_status,
        lease_verdict=(
            LeaseVerdictRead.model_validate(result.lease_verdict)
            if result.lease_verdict
            else None
        ),
    )


@router.get("/{application_id}/audit", response_model=list[AuditLogRead])
def get_audit_trail(
    application_id: uuid.UUID, db: DbSession, actor: CurrentActor
) -> list[AuditLogRead]:
    application = load_application(db, application_id)
    ensure_can_view(actor.role_enum, application)
    return [
        AuditLogRead.model_validate(entry)
        for entry in AuditService(db).timeline(application_id, limit=500)
    ]


# =============================================================================
# Documents
# =============================================================================


@router.get("/{application_id}/documents", response_model=list[DocumentRead])
def list_documents(
    application_id: uuid.UUID, db: DbSession, actor: CurrentActor
) -> list[DocumentRead]:
    application = load_application(db, application_id)
    ensure_can_view(actor.role_enum, application)
    stmt = (
        select(Document)
        .where(Document.application_id == application_id)
        .order_by(Document.uploaded_at.asc(), Document.version.asc())
    )
    return [DocumentRead.model_validate(doc) for doc in db.execute(stmt).scalars().all()]


@router.post(
    "/{application_id}/documents",
    status_code=status.HTTP_201_CREATED,
    response_model=DocumentRead,
)
def upload_document(
    application_id: uuid.UUID,
    db: DbSession,
    actor: CurrentActor,
    doc_type: Annotated[DocumentType, Form()],
    file: Annotated[UploadFile, File()],
    version: Annotated[int | None, Form(ge=1)] = None,
) -> DocumentRead:
    application = load_application(db, application_id)
    ensure_can_upload(actor.role_enum, application)
    settings = get_settings()

    mime_type = (file.content_type or "application/octet-stream").split(";")[0]
    if mime_type not in settings.allowed_upload_mime_types:
        raise ValidationFailure(
            f"Unsupported file type {mime_type!r}. Allowed: "
            f"{', '.join(settings.allowed_upload_mime_types)}.",
        )

    data = file.file.read()
    if not data:
        raise ValidationFailure("The uploaded file is empty.")
    if len(data) > settings.upload_max_bytes:
        raise ValidationFailure(
            f"File is {len(data) / 1_048_576:.1f} MB; the limit is "
            f"{settings.upload_max_bytes / 1_048_576:.0f} MB."
        )

    document_id = uuid.uuid4()
    stored = StorageService(settings).put(
        application_id=application.id,
        document_id=document_id,
        filename=file.filename or "document",
        data=data,
        mime_type=mime_type,
    )

    next_version = version or int(
        db.execute(
            select(func.coalesce(func.max(Document.version), 0)).where(
                Document.application_id == application.id,
                Document.doc_type == doc_type,
            )
        ).scalar_one()
    ) + 1

    document = Document(
        id=document_id,
        application_id=application.id,
        doc_type=doc_type,
        version=next_version,
        file_name=file.filename or stored.key.rsplit("/", 1)[-1],
        s3_url=stored.uri,
        mime_type=mime_type,
        size_bytes=stored.size_bytes,
        content_sha256=stored.sha256,
        uploaded_by=actor.id,
    )
    db.add(document)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(
            f"{doc_type.value} version {next_version} already exists for this docket."
        ) from exc

    db.refresh(document)
    AuditService(db).record(
        application=application,
        action="document.uploaded",
        actor=actor.id,
        actor_role=actor.role,
        payload={
            "document_id": str(document.id),
            "doc_type": document.doc_type.value,
            "version": document.version,
            "file_name": document.file_name,
            "content_sha256": document.content_sha256,
            "size_bytes": document.size_bytes,
        },
        commit=True,
    )

    if settings.celery_enabled and doc_type is DocumentType.LEASE_DEED:
        from app.workers.tasks import extract_document_task

        extract_document_task.delay(str(document.id))

    return DocumentRead.model_validate(document)
