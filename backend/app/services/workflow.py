"""Rule 2 — statutory triage state machine (APH 2024-27, Chapter II).

    Scrutiny ──(new / expansion)──► EVC ──► SAC ──► Approved | Rejected
        │                                    ▲  │
        └──(renewal / closure)───────────────┘  └──► SHC ──► Approved | Rejected

* ``NEW`` and ``EXPANSION`` applications must pass through an Expert Visit
  Committee (EVC); they cannot jump straight to the Standing/Scrutiny
  Committee.
* ``RENEWAL`` and ``CLOSURE`` skip the EVC and go straight to SAC.
* Rule 1 is a hard gate on the first move out of ``Scrutiny``.
* Every successful transition re-stamps ``stage_entry_timestamp`` (Rule 3) and
  writes a chained audit entry in the same transaction.

Transitions are executed under a row lock so two officers cannot double-advance
a docket.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy.orm import Session

from app.core.time import utcnow
from app.models import (
    Application,
    ApplicationStatus,
    ApplicationType,
    AuditLog,
)
from app.services.audit import AuditService
from app.services.compliance import LeaseVerdict, evaluate_live_lease
from app.services.errors import DomainError

TERMINAL_STATUSES: frozenset[ApplicationStatus] = frozenset(
    {ApplicationStatus.APPROVED, ApplicationStatus.REJECTED}
)

#: Application types that mandate an Expert Visit Committee.
EVC_REQUIRED_TYPES: frozenset[ApplicationType] = frozenset(
    {ApplicationType.NEW, ApplicationType.EXPANSION}
)


def allowed_transitions(application: Application) -> tuple[ApplicationStatus, ...]:
    """Legal next states for the application's current state and type."""
    status = application.status

    if status in TERMINAL_STATUSES:
        return ()

    if status is ApplicationStatus.SCRUTINY:
        if application.application_type in EVC_REQUIRED_TYPES:
            return (ApplicationStatus.EVC, ApplicationStatus.REJECTED)
        return (ApplicationStatus.SAC, ApplicationStatus.REJECTED)

    if status is ApplicationStatus.EVC:
        return (ApplicationStatus.SAC, ApplicationStatus.SHC)

    if status is ApplicationStatus.SAC:
        return (
            ApplicationStatus.APPROVED,
            ApplicationStatus.REJECTED,
            ApplicationStatus.SHC,
        )

    if status is ApplicationStatus.SHC:
        return (ApplicationStatus.APPROVED, ApplicationStatus.REJECTED)

    return ()


class WorkflowError(DomainError):
    code = "workflow_error"
    http_status = 409


class InvalidTransition(WorkflowError):
    code = "invalid_transition"


class LeaseRuleBlocked(WorkflowError):
    """Rule 1 refused the move out of Scrutiny."""

    code = "lease_rule_blocked"
    http_status = 422

    def __init__(self, verdict: LeaseVerdict) -> None:
        super().__init__(verdict.reason, context={"lease_verdict": verdict.as_dict()})
        self.verdict = verdict


@dataclass(frozen=True)
class TransitionResult:
    application: Application
    from_status: ApplicationStatus
    to_status: ApplicationStatus
    audit_log: AuditLog
    lease_verdict: LeaseVerdict | None


class WorkflowService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.audit = AuditService(db)

    def allowed(self, application: Application) -> tuple[ApplicationStatus, ...]:
        return allowed_transitions(application)

    def transition(
        self,
        application: Application,
        to_status: ApplicationStatus | str,
        *,
        actor: str,
        actor_role: str | None = None,
        remarks: str | None = None,
        occurred_at: datetime | None = None,
        as_of: date | None = None,
    ) -> TransitionResult:
        """Advance ``application`` or raise a domain error."""
        try:
            target = ApplicationStatus(to_status)
        except ValueError as exc:
            raise InvalidTransition(f"Unknown target status: {to_status!r}") from exc

        if application.id is None:
            raise WorkflowError("Cannot transition an unsaved application")

        # Serialise concurrent decisions on this docket.
        self.db.refresh(application, with_for_update=True)
        from_status = application.status

        if from_status in TERMINAL_STATUSES:
            raise InvalidTransition(
                f"Application {application.application_number} is already "
                f"{from_status.value} and cannot transition.",
                context={"status": from_status.value},
            )

        permitted = allowed_transitions(application)
        if target not in permitted:
            allowed_label = ", ".join(status.value for status in permitted) or "none"
            raise InvalidTransition(
                f"Illegal transition {from_status.value} → {target.value} for a "
                f"{application.application_type.value} application. "
                f"Allowed: {allowed_label}.",
                context={
                    "from_status": from_status.value,
                    "to_status": target.value,
                    "allowed": [status.value for status in permitted],
                    "application_type": application.application_type.value,
                },
            )

        lease_verdict: LeaseVerdict | None = None

        # --- Rule 1 gate: nothing leaves Scrutiny on an invalid lease --------
        if from_status is ApplicationStatus.SCRUTINY and target in (
            ApplicationStatus.EVC,
            ApplicationStatus.SAC,
        ):
            lease_verdict = evaluate_live_lease(self.db, application, as_of=as_of)
            if not lease_verdict.compliant:
                self.audit.record(
                    application=application,
                    action="lease_rule.blocked",
                    actor=actor,
                    actor_role=actor_role,
                    from_status=from_status,
                    to_status=None,
                    payload={
                        "attempted_transition": target.value,
                        "verdict": lease_verdict.as_dict(),
                    },
                    occurred_at=occurred_at,
                    commit=True,
                )
                raise LeaseRuleBlocked(lease_verdict)

        # --- Apply the transition -------------------------------------------
        timestamp = occurred_at or utcnow()
        application.status = target
        application.stage_entry_timestamp = timestamp  # Rule 3 clock restarts
        if target in TERMINAL_STATUSES:
            application.decided_at = timestamp
            application.decision_remarks = remarks

        audit_log = self.audit.record(
            application=application,
            action="stage.transition",
            actor=actor,
            actor_role=actor_role,
            from_status=from_status,
            to_status=target,
            payload={
                "remarks": remarks,
                "application_type": application.application_type.value,
                "lease_verdict": lease_verdict.as_dict() if lease_verdict else None,
            },
            occurred_at=timestamp,
        )

        self.db.commit()
        self.db.refresh(application)
        return TransitionResult(
            application=application,
            from_status=from_status,
            to_status=target,
            audit_log=audit_log,
            lease_verdict=lease_verdict,
        )
