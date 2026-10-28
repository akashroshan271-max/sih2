from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import (
    ApplicationStatus,
    ApplicationType,
    ProgrammeLevel,
)
from app.schemas.audit import AuditLogRead
from app.schemas.document import DocumentRead
from app.schemas.institution import InstitutionBrief


class ApplicationCreate(BaseModel):
    institution_id: uuid.UUID
    academic_year: str = Field(pattern=r"^\d{4}-\d{2}$", examples=["2026-27"])
    application_type: ApplicationType
    programme_level: ProgrammeLevel
    proposed_intake: int | None = Field(default=None, ge=0, le=100_000)
    max_course_duration_years: float | None = Field(
        default=None,
        gt=0,
        le=10,
        description="Defaults from programme level: diploma 3, UG 4, PG 2, integrated 5.",
    )
    submitted: bool = True


class LeaseVerdictRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    compliant: bool
    reason: str
    required_years: float
    remaining_lease_years: float | None = None
    lease_document_id: uuid.UUID | None = None
    lease_start_date: date | None = None
    lease_end_date: date | None = None
    as_of: date


class ApplicationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    application_number: str
    academic_year: str
    application_type: ApplicationType
    programme_level: ProgrammeLevel
    max_course_duration_years: float
    status: ApplicationStatus
    stage_entry_timestamp: datetime
    submitted_at: datetime | None = None
    decided_at: datetime | None = None
    proposed_intake: int | None = None

    # Derived on the model (Rule 3)
    dwell_days: float
    sla_due_at: datetime
    is_sla_breached: bool

    institution: InstitutionBrief


class ApplicationDetail(ApplicationRead):
    decision_remarks: str | None = None
    documents: list[DocumentRead] = Field(default_factory=list)
    audit_trail: list[AuditLogRead] = Field(default_factory=list)
    lease_verdict: LeaseVerdictRead | None = None
    allowed_transitions: list[ApplicationStatus] = Field(default_factory=list)


class ApplicationListResponse(BaseModel):
    items: list[ApplicationRead]
    total: int
    limit: int
    offset: int


class TransitionRequest(BaseModel):
    to_status: ApplicationStatus
    remarks: str | None = Field(default=None, max_length=2000)


class TransitionResponse(BaseModel):
    application: ApplicationDetail
    audit_log: AuditLogRead
    from_status: ApplicationStatus
    to_status: ApplicationStatus
    lease_verdict: LeaseVerdictRead | None = None


class DocumentExtractionResponse(BaseModel):
    document: DocumentRead
    lease_verdict: LeaseVerdictRead | None = None
