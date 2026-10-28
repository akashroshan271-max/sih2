from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.models import ApplicationStatus
from app.schemas.application import ApplicationRead


class StageDwellRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: ApplicationStatus
    count: int
    avg_dwell_days: float
    max_dwell_days: float
    breached: int


class KpiResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total_active: int
    dwell_alerts: int
    lease_expiry_warnings: int
    lease_data_gaps: int
    lease_rule_blocks: int
    approved: int
    rejected: int
    approval_rate: float | None = None
    avg_dwell_days: float | None = None
    generated_at: datetime
    stages: list[StageDwellRead]


class PipelineColumnRead(BaseModel):
    status: ApplicationStatus
    count: int
    applications: list[ApplicationRead]


class PipelineResponse(BaseModel):
    columns: list[PipelineColumnRead]
    generated_at: datetime


class HeatmapCellRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    state: str
    status: ApplicationStatus
    count: int
    avg_dwell_days: float
    breached: int


class HeatmapResponse(BaseModel):
    cells: list[HeatmapCellRead]
    states: list[str]
    stages: list[ApplicationStatus]
    threshold_days: int


class FunnelStepRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: ApplicationStatus
    count: int
    share: float


class FunnelResponse(BaseModel):
    steps: list[FunnelStepRead]
    total: int


class LeaseWarningRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    application_id: uuid.UUID
    application_number: str
    institution_name: str
    state: str
    status: ApplicationStatus
    code: str
    lease_end_date: date | None = None
    remaining_lease_years: float | None = None
    required_years: float
    document_id: uuid.UUID | None = None


class LeaseWarningListResponse(BaseModel):
    items: list[LeaseWarningRead]
    total: int
    generated_at: datetime


class SlaAlertRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    application_id: uuid.UUID
    application_number: str
    institution_name: str
    state: str
    status: ApplicationStatus
    stage_entry_timestamp: datetime
    dwell_days: float
    sla_due_at: datetime
    level: str
    escalate_to: str
    severity: str


class SlaAlertListResponse(BaseModel):
    items: list[SlaAlertRead]
    total: int
    levels: dict[str, int]
    generated_at: datetime


class SlaScanResponse(BaseModel):
    scanned_at: datetime
    checked: int
    overdue: int
    escalated: int
    levels: dict[str, int]
