"""Regional Officer command-centre aggregations."""

from __future__ import annotations

from collections import Counter
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentActor, DbSession, require_roles
from app.core.config import get_settings
from app.core.time import utcnow
from app.models import OfficerRole
from app.schemas.application import ApplicationRead
from app.schemas.dashboard import (
    FunnelResponse,
    FunnelStepRead,
    HeatmapCellRead,
    HeatmapResponse,
    KpiResponse,
    LeaseWarningListResponse,
    LeaseWarningRead,
    PipelineColumnRead,
    PipelineResponse,
    SlaAlertListResponse,
    SlaAlertRead,
    SlaScanResponse,
)
from app.services import analytics
from app.services.sla import SlaService

#: The command centre is the Regional Officer's oversight surface; stage desks
#: use /workspace instead and never see cross-region aggregates.
router = APIRouter(
    prefix="/dashboard",
    tags=["dashboard"],
    dependencies=[Depends(require_roles(OfficerRole.REGIONAL_OFFICER))],
)


@router.get("/kpis", response_model=KpiResponse)
def get_kpis(db: DbSession) -> KpiResponse:
    return KpiResponse.model_validate(analytics.kpis(db))


@router.get("/pipeline", response_model=PipelineResponse)
def get_pipeline(
    db: DbSession,
    per_stage: Annotated[int, Query(ge=1, le=50)] = 8,
) -> PipelineResponse:
    columns = analytics.pipeline(db, per_stage=per_stage)
    return PipelineResponse(
        columns=[
            PipelineColumnRead(
                status=column.status,
                count=column.count,
                applications=[
                    ApplicationRead.model_validate(application)
                    for application in column.applications
                ],
            )
            for column in columns
        ],
        generated_at=utcnow(),
    )


@router.get("/sla-heatmap", response_model=HeatmapResponse)
def get_heatmap(db: DbSession) -> HeatmapResponse:
    config = get_settings()
    cells = analytics.heatmap(db, settings=config)
    return HeatmapResponse(
        cells=[HeatmapCellRead.model_validate(cell) for cell in cells],
        states=sorted({cell.state for cell in cells}),
        stages=[status for status in analytics.PIPELINE_ORDER],
        threshold_days=config.sla_threshold_days,
    )


@router.get("/funnel", response_model=FunnelResponse)
def get_funnel(db: DbSession) -> FunnelResponse:
    steps = analytics.funnel(db)
    return FunnelResponse(
        steps=[FunnelStepRead.model_validate(step) for step in steps],
        total=sum(step.count for step in steps),
    )


@router.get("/sla-alerts", response_model=SlaAlertListResponse)
def get_sla_alerts(db: DbSession) -> SlaAlertListResponse:
    alerts = SlaService(db).alerts()
    levels = Counter(alert.level for alert in alerts)
    return SlaAlertListResponse(
        items=[SlaAlertRead.model_validate(alert) for alert in alerts],
        total=len(alerts),
        levels=dict(levels),
        generated_at=utcnow(),
    )


@router.post("/sla/scan", response_model=SlaScanResponse)
def run_sla_scan(db: DbSession, actor: CurrentActor) -> SlaScanResponse:
    """Manual escalation sweep (the Celery beat job calls the same service)."""
    result = SlaService(db).scan(actor=actor.id, actor_role=actor.role)
    return SlaScanResponse(
        scanned_at=result.scanned_at,
        checked=result.checked,
        overdue=result.overdue,
        escalated=len(result.escalated),
        levels=result.levels,
    )


@router.get("/lease-warnings", response_model=LeaseWarningListResponse)
def get_lease_warnings(db: DbSession) -> LeaseWarningListResponse:
    warnings = analytics.lease_warnings(db)
    return LeaseWarningListResponse(
        items=[LeaseWarningRead.model_validate(warning) for warning in warnings],
        total=len(warnings),
        generated_at=utcnow(),
    )
