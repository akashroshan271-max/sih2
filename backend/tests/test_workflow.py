"""Rule 2 — statutory triage state machine."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.core.time import as_utc
from app.models import ApplicationStatus, ApplicationType
from app.services.audit import AuditService
from app.services.workflow import (
    InvalidTransition,
    WorkflowService,
    allowed_transitions,
)

TODAY = date.today()


def _lease(make_lease, application, years: int = 8):
    make_lease(
        application,
        start=TODAY - timedelta(days=365),
        end=TODAY + timedelta(days=365 * years),
    )


def test_new_application_cannot_skip_evc(make_application, make_lease, db):
    application = make_application(application_type=ApplicationType.NEW)
    _lease(make_lease, application)

    with pytest.raises(InvalidTransition) as excinfo:
        WorkflowService(db).transition(
            application, ApplicationStatus.SAC, actor="officer@aicte.gov.in"
        )

    assert "evc" in str(excinfo.value)
    assert excinfo.value.context["allowed"] == ["evc", "rejected"]
    db.refresh(application)
    assert application.status is ApplicationStatus.SCRUTINY


def test_expansion_requires_evc_and_renewal_does_not(make_application):
    expansion = make_application(application_type=ApplicationType.EXPANSION)
    renewal = make_application(application_type=ApplicationType.RENEWAL)
    closure = make_application(application_type=ApplicationType.CLOSURE)

    assert allowed_transitions(expansion) == (
        ApplicationStatus.EVC,
        ApplicationStatus.REJECTED,
    )
    assert allowed_transitions(renewal) == (
        ApplicationStatus.SAC,
        ApplicationStatus.REJECTED,
    )
    assert allowed_transitions(closure) == (
        ApplicationStatus.SAC,
        ApplicationStatus.REJECTED,
    )


def test_full_new_application_journey(make_application, make_lease, db):
    application = make_application(application_type=ApplicationType.NEW)
    _lease(make_lease, application)
    service = WorkflowService(db)

    first = service.transition(
        application,
        ApplicationStatus.EVC,
        actor="scrutiny.officer@aicte.gov.in",
        remarks="Documents complete; EVC required for new programme.",
    )
    assert first.from_status is ApplicationStatus.SCRUTINY
    assert first.to_status is ApplicationStatus.EVC
    assert first.lease_verdict is not None and first.lease_verdict.compliant

    second = service.transition(
        application, ApplicationStatus.SAC, actor="evc.chair@aicte.gov.in"
    )
    assert second.to_status is ApplicationStatus.SAC

    approved = service.transition(
        application,
        ApplicationStatus.APPROVED,
        actor="sac.chair@aicte.gov.in",
        remarks="Approved for 2026-27 with intake of 420.",
    )
    assert approved.to_status is ApplicationStatus.APPROVED

    db.refresh(application)
    assert application.status is ApplicationStatus.APPROVED
    assert application.decided_at is not None
    assert application.decision_remarks.startswith("Approved for 2026-27")
    assert application.stage_entry_timestamp == approved.application.stage_entry_timestamp

    timeline = AuditService(db).timeline(application.id)
    assert [entry.action for entry in timeline] == [
        "stage.transition",
        "stage.transition",
        "stage.transition",
    ]
    assert AuditService(db).verify(application.id).valid
    # Hash chain: each entry links to its predecessor.
    assert timeline[0].previous_hash is None
    assert timeline[1].previous_hash == timeline[0].sha256_hash
    assert timeline[2].previous_hash == timeline[1].sha256_hash


def test_each_transition_restarts_the_sla_clock(make_application, make_lease, db):
    application = make_application(age_days=21)
    _lease(make_lease, application)

    assert application.dwell_days == pytest.approx(21, abs=0.05)
    before = as_utc(application.stage_entry_timestamp)

    service = WorkflowService(db)
    service.transition(application, ApplicationStatus.EVC, actor="officer@aicte.gov.in")

    db.refresh(application)
    after = as_utc(application.stage_entry_timestamp)
    assert after > before
    assert application.dwell_days < 0.01


def test_evc_cannot_go_straight_to_approval(make_application, make_lease, db):
    application = make_application(status=ApplicationStatus.EVC)
    _lease(make_lease, application)

    with pytest.raises(InvalidTransition):
        WorkflowService(db).transition(
            application, ApplicationStatus.APPROVED, actor="officer@aicte.gov.in"
        )


def test_rejection_is_terminal(make_application, db):
    application = make_application()
    service = WorkflowService(db)

    result = service.transition(
        application,
        ApplicationStatus.REJECTED,
        actor="officer@aicte.gov.in",
        remarks="Deficient land documents.",
    )
    assert result.to_status is ApplicationStatus.REJECTED
    assert allowed_transitions(application) == ()

    with pytest.raises(InvalidTransition) as excinfo:
        service.transition(application, ApplicationStatus.EVC, actor="officer@aicte.gov.in")

    assert "already rejected" in str(excinfo.value)


def test_invalid_target_status_is_rejected(make_application, db):
    application = make_application()

    with pytest.raises(InvalidTransition):
        WorkflowService(db).transition(application, "approved-please", actor="officer")  # type: ignore[arg-type]


def test_actor_is_recorded_in_the_trail(make_application, db):
    application = make_application()
    WorkflowService(db).transition(
        application,
        ApplicationStatus.REJECTED,
        actor="ro.mumbai@aicte.gov.in",
        actor_role="regional_officer",
        remarks="Lease not registered.",
    )
    entry = AuditService(db).timeline(application.id)[-1]

    assert entry.actor == "ro.mumbai@aicte.gov.in"
    assert entry.actor_role == "regional_officer"
    assert entry.from_status is ApplicationStatus.SCRUTINY
    assert entry.to_status is ApplicationStatus.REJECTED
