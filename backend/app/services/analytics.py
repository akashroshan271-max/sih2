"""Dashboard aggregations for the Regional Officer command centre.

All maths is done in Python over bounded, indexed queries so the same code runs
against PostgreSQL and the SQLite test database (no dialect-specific date
arithmetic). Volumes here are regional, not national: a few thousand active
dockets per officer.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import Settings, get_settings
from app.core.time import as_utc, utcnow
from app.models import (
    ACTIVE_STAGES,
    Application,
    ApplicationStatus,
    AuditLog,
    Document,
    DocumentType,
    Institution,
)
from app.services.compliance import DAYS_PER_YEAR

PIPELINE_ORDER: tuple[ApplicationStatus, ...] = (
    ApplicationStatus.SCRUTINY,
    ApplicationStatus.EVC,
    ApplicationStatus.SAC,
    ApplicationStatus.SHC,
)


@dataclass(frozen=True)
class StageDwell:
    status: ApplicationStatus
    count: int
    avg_dwell_days: float
    max_dwell_days: float
    breached: int


@dataclass(frozen=True)
class LeaseWarning:
    application_id: uuid.UUID
    application_number: str
    institution_name: str
    state: str
    status: ApplicationStatus
    code: str
    lease_end_date: date | None
    remaining_lease_years: float | None
    required_years: float
    document_id: uuid.UUID | None


@dataclass(frozen=True)
class KpiSnapshot:
    total_active: int
    dwell_alerts: int
    lease_expiry_warnings: int
    lease_data_gaps: int
    lease_rule_blocks: int
    approved: int
    rejected: int
    approval_rate: float | None
    avg_dwell_days: float | None
    generated_at: datetime
    stages: tuple[StageDwell, ...]


@dataclass(frozen=True)
class PipelineColumn:
    status: ApplicationStatus
    count: int
    applications: list[Application]


@dataclass(frozen=True)
class HeatmapCell:
    state: str
    status: ApplicationStatus
    count: int
    avg_dwell_days: float
    breached: int


@dataclass(frozen=True)
class FunnelStep:
    status: ApplicationStatus
    count: int
    share: float


# =============================================================================
# Helpers
# =============================================================================


def _dwell_days(entered: datetime, now: datetime) -> float:
    return (now - as_utc(entered)).total_seconds() / 86_400


def _dwell_buckets(
    db: Session, now: datetime
) -> dict[ApplicationStatus, list[float]]:
    """One query: dwell days per active application, bucketed by stage."""
    stmt = select(Application.status, Application.stage_entry_timestamp).where(
        Application.status.in_(tuple(ACTIVE_STAGES))
    )
    buckets: dict[ApplicationStatus, list[float]] = defaultdict(list)
    for status, entered in db.execute(stmt).all():
        buckets[status].append(_dwell_days(entered, now))
    return buckets


def _stage_dwells(
    buckets: dict[ApplicationStatus, list[float]], settings: Settings
) -> tuple[StageDwell, ...]:
    stages: list[StageDwell] = []
    for status in PIPELINE_ORDER:
        samples = buckets.get(status, [])
        stages.append(
            StageDwell(
                status=status,
                count=len(samples),
                avg_dwell_days=round(sum(samples) / len(samples), 2) if samples else 0.0,
                max_dwell_days=round(max(samples), 2) if samples else 0.0,
                breached=sum(1 for dwell in samples if dwell > settings.sla_threshold_days),
            )
        )
    return tuple(stages)


def stage_dwells(
    db: Session,
    *,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> tuple[StageDwell, ...]:
    config = settings or get_settings()
    moment = as_utc(now or utcnow())
    return _stage_dwells(_dwell_buckets(db, moment), config)


def lease_warnings(
    db: Session,
    *,
    now: datetime | None = None,
) -> list[LeaseWarning]:
    """Active dockets that cannot satisfy Rule 1 (expiry or missing data)."""
    moment = as_utc(now or utcnow())
    today = moment.date()

    stmt = (
        select(Application, Institution, Document)
        .join(Institution, Institution.id == Application.institution_id)
        .join(
            Document,
            and_(
                Document.application_id == Application.id,
                Document.doc_type == DocumentType.LEASE_DEED,
            ),
        )
        .where(Application.status.in_(tuple(ACTIVE_STAGES)))
        .order_by(Application.id, Document.version.desc())
    )
    by_application: dict[uuid.UUID, tuple[Application, Institution, Document]] = {}
    for application, institution, document in db.execute(stmt).all():
        by_application.setdefault(application.id, (application, institution, document))

    warnings: list[LeaseWarning] = []
    for application, institution, document in by_application.values():
        required = float(application.max_course_duration_years)

        if document.lease_start_date is None or document.lease_end_date is None:
            warnings.append(
                LeaseWarning(
                    application_id=application.id,
                    application_number=application.application_number,
                    institution_name=institution.name,
                    state=institution.state,
                    status=application.status,
                    code="lease_not_extracted",
                    lease_end_date=None,
                    remaining_lease_years=None,
                    required_years=required,
                    document_id=document.id,
                )
            )
            continue

        remaining = (document.lease_end_date - today).days / DAYS_PER_YEAR
        if remaining < 0:
            code = "lease_expired"
        elif remaining < required:
            code = "lease_too_short"
        else:
            continue

        warnings.append(
            LeaseWarning(
                application_id=application.id,
                application_number=application.application_number,
                institution_name=institution.name,
                state=institution.state,
                status=application.status,
                code=code,
                lease_end_date=document.lease_end_date,
                remaining_lease_years=round(remaining, 2),
                required_years=required,
                document_id=document.id,
            )
        )

    # Dockets with no lease deed at all cannot be evaluated either.
    with_deed = set(by_application)
    rows = db.execute(
        select(Application, Institution)
        .join(Institution, Institution.id == Application.institution_id)
        .where(Application.status.in_(tuple(ACTIVE_STAGES)))
    ).all()
    for application, institution in rows:
        if application.id in with_deed:
            continue
        warnings.append(
            LeaseWarning(
                application_id=application.id,
                application_number=application.application_number,
                institution_name=institution.name,
                state=institution.state,
                status=application.status,
                code="lease_deed_missing",
                lease_end_date=None,
                remaining_lease_years=None,
                required_years=float(application.max_course_duration_years),
                document_id=None,
            )
        )

    warnings.sort(key=lambda warning: warning.remaining_lease_years or -1_000)
    return warnings


def kpis(
    db: Session,
    *,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> KpiSnapshot:
    config = settings or get_settings()
    moment = as_utc(now or utcnow())
    cutoff = moment - timedelta(days=config.sla_threshold_days)

    total_active = int(
        db.execute(
            select(func.count())
            .select_from(Application)
            .where(Application.status.in_(tuple(ACTIVE_STAGES)))
        ).scalar_one()
    )
    dwell_alerts = int(
        db.execute(
            select(func.count())
            .select_from(Application)
            .where(
                Application.status.in_(tuple(ACTIVE_STAGES)),
                Application.stage_entry_timestamp < cutoff,
            )
        ).scalar_one()
    )
    approved = int(
        db.execute(
            select(func.count())
            .select_from(Application)
            .where(Application.status == ApplicationStatus.APPROVED)
        ).scalar_one()
    )
    rejected = int(
        db.execute(
            select(func.count())
            .select_from(Application)
            .where(Application.status == ApplicationStatus.REJECTED)
        ).scalar_one()
    )
    lease_rule_blocks = int(
        db.execute(
            select(func.count())
            .select_from(AuditLog)
            .where(AuditLog.action == "lease_rule.blocked")
        ).scalar_one()
    )

    warnings = lease_warnings(db, now=moment)
    expiry_warnings = [w for w in warnings if w.remaining_lease_years is not None]
    gaps = [w for w in warnings if w.remaining_lease_years is None]

    buckets = _dwell_buckets(db, moment)
    stages = _stage_dwells(buckets, config)
    dwells = [dwell for samples in buckets.values() for dwell in samples]

    decided = approved + rejected
    return KpiSnapshot(
        total_active=total_active,
        dwell_alerts=dwell_alerts,
        lease_expiry_warnings=len(expiry_warnings),
        lease_data_gaps=len(gaps),
        lease_rule_blocks=lease_rule_blocks,
        approved=approved,
        rejected=rejected,
        approval_rate=round(approved / decided, 4) if decided else None,
        avg_dwell_days=round(sum(dwells) / len(dwells), 2) if dwells else None,
        generated_at=moment,
        stages=stages,
    )


def pipeline(
    db: Session,
    *,
    per_stage: int = 8,
) -> list[PipelineColumn]:
    columns: list[PipelineColumn] = []
    for status in PIPELINE_ORDER:
        total = int(
            db.execute(
                select(func.count())
                .select_from(Application)
                .where(Application.status == status)
            ).scalar_one()
        )
        stmt = (
            select(Application)
            .options(selectinload(Application.institution))
            .where(Application.status == status)
            .order_by(Application.stage_entry_timestamp.asc())
            .limit(per_stage)
        )
        applications = list(db.execute(stmt).scalars().all())
        columns.append(PipelineColumn(status=status, count=total, applications=applications))
    return columns


def heatmap(
    db: Session,
    *,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> list[HeatmapCell]:
    """State × stage dwell matrix powering the SLA heatmap."""
    config = settings or get_settings()
    moment = as_utc(now or utcnow())

    rows = db.execute(
        select(Institution.state, Application.status, Application.stage_entry_timestamp)
        .join(Institution, Institution.id == Application.institution_id)
        .where(Application.status.in_(tuple(ACTIVE_STAGES)))
    ).all()

    grouped: dict[tuple[str, ApplicationStatus], list[float]] = defaultdict(list)
    for state, status, entered in rows:
        grouped[(state, status)].append(_dwell_days(entered, moment))

    cells: list[HeatmapCell] = []
    for state in sorted({state for state, _ in grouped}):
        for status in PIPELINE_ORDER:
            samples = grouped.get((state, status), [])
            cells.append(
                HeatmapCell(
                    state=state,
                    status=status,
                    count=len(samples),
                    avg_dwell_days=round(sum(samples) / len(samples), 2) if samples else 0.0,
                    breached=sum(
                        1 for dwell in samples if dwell > config.sla_threshold_days
                    ),
                )
            )
    return cells


def funnel(db: Session) -> list[FunnelStep]:
    """Volume per stage across the whole lifecycle (approved funnel chart)."""
    counts = dict(
        db.execute(
            select(Application.status, func.count()).group_by(Application.status)
        ).all()
    )
    total = sum(counts.values())
    return [
        FunnelStep(
            status=status,
            count=int(counts.get(status, 0)),
            share=round(counts.get(status, 0) / total, 4) if total else 0.0,
        )
        for status in (*PIPELINE_ORDER, ApplicationStatus.APPROVED, ApplicationStatus.REJECTED)
    ]
