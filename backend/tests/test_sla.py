"""Rule 3 — SLA dwell-time monitoring and hierarchical escalation."""

from __future__ import annotations

from datetime import date, timedelta

from app.core.time import utcnow
from app.models import ApplicationStatus, ApplicationType
from app.services.audit import AuditService
from app.services.sla import SlaService, escalation_tiers

TODAY = date.today()


def test_escalation_tiers_are_ordered():
    tiers = escalation_tiers()

    assert [tier.level for tier in tiers] == ["L1", "L2", "L3"]
    assert [tier.threshold_days for tier in tiers] == [15, 30, 45]


def test_alert_levels_by_dwell(make_application, db):
    make_application(age_days=20, application_type=ApplicationType.NEW)
    make_application(age_days=35, application_type=ApplicationType.EXPANSION)
    make_application(age_days=50, application_type=ApplicationType.RENEWAL)

    alerts = SlaService(db).alerts()

    assert len(alerts) == 3
    levels = {round(alert.dwell_days): alert.level for alert in alerts}
    assert levels[20] == "L1"
    assert levels[35] == "L2"
    assert levels[50] == "L3"
    assert {alert.escalate_to for alert in alerts} == {
        "Concerned Dealing Officer",
        "Regional Officer",
        "Chairman, AICTE",
    }
    assert {alert.severity for alert in alerts} == {"warning", "high", "critical"}


def test_fresh_and_terminal_dockets_are_not_flagged(make_application, db):
    make_application(age_days=3, application_type=ApplicationType.NEW)
    make_application(
        status=ApplicationStatus.APPROVED,
        age_days=60,
        application_type=ApplicationType.EXPANSION,
    )
    make_application(
        status=ApplicationStatus.REJECTED,
        age_days=60,
        application_type=ApplicationType.RENEWAL,
    )

    assert SlaService(db).alerts() == []


def test_scan_escalates_once_and_is_idempotent(make_application, db):
    overdue = make_application(age_days=40)
    service = SlaService(db)

    first = service.scan(actor="system:celery")
    assert first.overdue == 1
    assert len(first.escalated) == 1
    assert first.levels == {"L2": 1}
    assert first.checked == 1

    second = service.scan(actor="system:celery")
    assert second.overdue == 1
    assert second.escalated == []

    entries = [
        entry
        for entry in AuditService(db).timeline(overdue.id)
        if entry.action.startswith("sla.escalation.")
    ]
    assert len(entries) == 1
    assert entries[0].action == "sla.escalation.L2"
    assert entries[0].actor == "system:celery"
    assert entries[0].payload["escalate_to"] == "Regional Officer"
    assert AuditService(db).verify(overdue.id).valid


def test_escalation_repeats_after_a_new_stage_entry(make_application, db):
    application = make_application(age_days=20)
    service = SlaService(db)
    service.scan()
    service.scan()

    # A transition restarts the clock; once it ages past L1 again a fresh
    # escalation must be written for the new stage entry.
    application.stage_entry_timestamp = utcnow() - timedelta(days=20)
    db.commit()

    result = service.scan()
    assert len(result.escalated) == 1
    assert result.escalated[0].level == "L1"

    actions = [
        entry.action
        for entry in AuditService(db).timeline(application.id)
        if entry.action.startswith("sla.escalation.")
    ]
    assert actions == ["sla.escalation.L1", "sla.escalation.L1"]


def test_transition_clears_the_alert(make_application, make_lease, db):
    application = make_application(age_days=20)
    make_lease(
        application,
        start=TODAY - timedelta(days=365),
        end=TODAY + timedelta(days=3000),
    )
    service = SlaService(db)
    assert len(service.alerts()) == 1

    from app.services.workflow import WorkflowService

    WorkflowService(db).transition(
        application, ApplicationStatus.EVC, actor="officer@aicte.gov.in"
    )

    assert service.alerts() == []
