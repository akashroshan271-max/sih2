"""Rule 3 — SLA dwell-time monitoring and hierarchical escalation.

A docket may not sit in one stage for more than the configured threshold
(APH 2024-27: 15 days). Escalation is layered:

    L1  > 15 days  → Concerned Dealing Officer   (warning)
    L2  > 30 days  → Regional Officer           (high)
    L3  > 45 days  → Chairman, AICTE            (critical)

The Celery beat job calls :meth:`SlaService.scan`, which is idempotent: for a
given application, stage entry and level it writes at most one escalation
audit entry, so hourly sweeps do not spam the trail.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.time import as_utc, isoformat_utc, utcnow
from app.models import (
    ACTIVE_STAGES,
    Application,
    ApplicationStatus,
    AuditLog,
    Institution,
)
from app.services.audit import AuditService

SEVERITY: dict[str, str] = {"L1": "warning", "L2": "high", "L3": "critical"}


@dataclass(frozen=True)
class EscalationTier:
    level: str
    threshold_days: int
    escalate_to: str


def escalation_tiers(settings: Settings | None = None) -> tuple[EscalationTier, ...]:
    config = settings or get_settings()
    tiers = (
        EscalationTier("L1", config.sla_threshold_days, "Concerned Dealing Officer"),
        EscalationTier("L2", config.escalation_l2_days, "Regional Officer"),
        EscalationTier("L3", config.escalation_l3_days, "Chairman, AICTE"),
    )
    return tuple(sorted(tiers, key=lambda tier: tier.threshold_days))


@dataclass(frozen=True)
class SlaAlert:
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

    def as_payload(self) -> dict[str, object]:
        return {
            "level": self.level,
            "escalate_to": self.escalate_to,
            "severity": self.severity,
            "status": self.status.value,
            "dwell_days": round(self.dwell_days, 2),
            "stage_entry_timestamp": isoformat_utc(self.stage_entry_timestamp),
            "sla_due_at": isoformat_utc(self.sla_due_at),
        }


@dataclass
class SlaScanResult:
    scanned_at: datetime
    checked: int = 0
    overdue: int = 0
    escalated: list[SlaAlert] = field(default_factory=list)
    alerts: list[SlaAlert] = field(default_factory=list)

    @property
    def levels(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for alert in self.alerts:
            counts[alert.level] = counts.get(alert.level, 0) + 1
        return counts


class SlaService:
    def __init__(self, db: Session, settings: Settings | None = None) -> None:
        self.db = db
        self.settings = settings or get_settings()
        self.tiers = escalation_tiers(self.settings)
        self.audit = AuditService(db)

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------
    def alerts(self, *, now: datetime | None = None) -> list[SlaAlert]:
        """All active dockets currently past at least the L1 threshold."""
        moment = as_utc(now or utcnow())
        minimum = self.tiers[0].threshold_days
        cutoff = moment - timedelta(days=minimum)

        stmt = (
            select(Application, Institution)
            .join(Institution, Institution.id == Application.institution_id)
            .where(
                Application.status.in_(tuple(ACTIVE_STAGES)),
                Application.stage_entry_timestamp < cutoff,
            )
            .order_by(Application.stage_entry_timestamp.asc())
        )
        rows = self.db.execute(stmt).all()

        alerts: list[SlaAlert] = []
        for application, institution in rows:
            entered = as_utc(application.stage_entry_timestamp)
            dwell = (moment - entered).total_seconds() / 86_400
            tier = self._tier_for(dwell)
            if tier is None:
                continue
            alerts.append(
                SlaAlert(
                    application_id=application.id,
                    application_number=application.application_number,
                    institution_name=institution.name,
                    state=institution.state,
                    status=application.status,
                    stage_entry_timestamp=entered,
                    dwell_days=dwell,
                    sla_due_at=entered + timedelta(days=self.settings.sla_threshold_days),
                    level=tier.level,
                    escalate_to=tier.escalate_to,
                    severity=SEVERITY.get(tier.level, "warning"),
                )
            )
        return alerts

    def _tier_for(self, dwell_days: float) -> EscalationTier | None:
        matched: EscalationTier | None = None
        for tier in self.tiers:
            if dwell_days > tier.threshold_days:
                matched = tier
        return matched

    # ------------------------------------------------------------------
    # Escalation (Celery / manual trigger)
    # ------------------------------------------------------------------
    def scan(
        self,
        *,
        now: datetime | None = None,
        actor: str = "system:celery",
        actor_role: str = "system",
        persist: bool = True,
    ) -> SlaScanResult:
        moment = as_utc(now or utcnow())
        alerts = self.alerts(now=moment)
        result = SlaScanResult(scanned_at=moment, alerts=alerts, overdue=len(alerts))

        if persist:
            for alert in alerts:
                if self._already_escalated(alert):
                    continue
                application = self.db.get(Application, alert.application_id)
                if application is None:  # pragma: no cover - row deleted mid-sweep
                    continue
                self.audit.record(
                    application=application,
                    action=f"sla.escalation.{alert.level}",
                    actor=actor,
                    actor_role=actor_role,
                    from_status=application.status,
                    to_status=application.status,
                    payload=alert.as_payload(),
                    occurred_at=moment,
                )
                result.escalated.append(alert)
            self.db.commit()

        result.checked = int(
            self.db.execute(
                select(func.count())
                .select_from(Application)
                .where(Application.status.in_(tuple(ACTIVE_STAGES)))
            ).scalar_one()
        )
        return result

    def _already_escalated(self, alert: SlaAlert) -> bool:
        entries = self.db.execute(
            select(AuditLog.payload).where(
                AuditLog.application_id == alert.application_id,
                AuditLog.action == f"sla.escalation.{alert.level}",
            )
        ).scalars().all()
        stage_marker = isoformat_utc(alert.stage_entry_timestamp)
        return any((entry or {}).get("stage_entry_timestamp") == stage_marker for entry in entries)
