"""Role-scoped workspace payloads.

The workspace is deliberately *not* the regional dashboard. Each desk receives
only the dockets sitting at its own stage, the facts that stage is required to
verify, and the moves it is competent to make — plus a short mandate so the
officer knows what they are accountable for.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models import (
    ApplicationStatus,
    ApplicationType,
    DocumentType,
    ExtractionStatus,
    InstitutionType,
    OfficerRole,
    ProgrammeLevel,
)
from app.schemas.auth import OfficerRead
from app.schemas.dashboard import SlaAlertRead

KpiTone = Literal["neutral", "teal", "turmeric", "seal"]


class DeskRead(BaseModel):
    role: OfficerRole
    label: str
    stage: ApplicationStatus | None = None
    stage_label: str
    mandate: str
    checklist: list[str] = Field(default_factory=list)
    next_step: str
    authority: str


class WorkspaceKpiRead(BaseModel):
    key: str
    label: str
    value: float
    unit: str | None = None
    tone: KpiTone = "neutral"
    hint: str | None = None


class LeaseSnapshotRead(BaseModel):
    document_id: uuid.UUID | None = None
    version: int | None = None
    extraction_status: ExtractionStatus | None = None
    lease_start_date: date | None = None
    lease_end_date: date | None = None
    remaining_years: float | None = None
    required_years: float
    total_land_area_sqm: float | None = None
    survey_numbers: list[str] = Field(default_factory=list)
    verdict_code: str
    verdict_reason: str
    compliant: bool


class WorkspaceDocumentRead(BaseModel):
    id: uuid.UUID
    doc_type: DocumentType
    version: int
    file_name: str
    extraction_status: ExtractionStatus
    uploaded_at: datetime
    lease_start_date: date | None = None
    lease_end_date: date | None = None
    size_bytes: int | None = None


class WorkspaceFactRead(BaseModel):
    label: str
    value: str
    note: str | None = None


class WorkspaceActionRead(BaseModel):
    to_status: ApplicationStatus
    label: str
    enabled: bool = True
    blocked_reason: str | None = None
    requires_note: bool = False
    is_decision: bool = False


class WorkspaceActivityRead(BaseModel):
    action: str
    actor: str
    actor_role: str | None = None
    timestamp: datetime
    from_status: ApplicationStatus | None = None
    to_status: ApplicationStatus | None = None


class WorkspaceDocketRead(BaseModel):
    id: uuid.UUID
    application_number: str
    institution_name: str
    state: str
    district: str | None = None
    institution_type: InstitutionType
    approved_intake: int
    academic_year: str
    application_type: ApplicationType
    programme_level: ProgrammeLevel
    proposed_intake: int | None = None
    max_course_duration_years: float

    status: ApplicationStatus
    stage_entry_timestamp: datetime
    dwell_days: float
    sla_due_at: datetime
    is_sla_breached: bool
    submitted_at: datetime | None = None
    decided_at: datetime | None = None

    lease: LeaseSnapshotRead | None = None
    documents: list[WorkspaceDocumentRead] = Field(default_factory=list)
    facts: list[WorkspaceFactRead] = Field(default_factory=list)
    actions: list[WorkspaceActionRead] = Field(default_factory=list)
    last_activity: WorkspaceActivityRead | None = None


class WorkspaceResponse(BaseModel):
    generated_at: datetime
    officer: OfficerRead
    desk: DeskRead
    notice: str | None = None
    kpis: list[WorkspaceKpiRead] = Field(default_factory=list)
    queue: list[WorkspaceDocketRead] = Field(default_factory=list)
    queue_total: int = 0
    stage_counts: dict[str, int] = Field(default_factory=dict)
    escalations: list[SlaAlertRead] = Field(default_factory=list)
