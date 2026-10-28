"""Rule 1 — APH 2024-27 Cl. 2.1.e live-lease compliance."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.models import ApplicationStatus, ApplicationType, ExtractionStatus
from app.services.audit import AuditService
from app.services.compliance import (
    DAYS_PER_YEAR,
    LEASE_DEED_MISSING,
    LEASE_EXPIRED,
    LEASE_NOT_COMMENCED,
    LEASE_NOT_EXTRACTED,
    LEASE_TOO_SHORT,
    LEASE_VALID,
    evaluate_live_lease,
)
from app.services.workflow import InvalidTransition, LeaseRuleBlocked, WorkflowService

TODAY = date.today()


def test_valid_lease_satisfies_rule(make_application, make_lease, db):
    application = make_application(duration=4.0)
    make_lease(
        application,
        start=TODAY - timedelta(days=730),
        end=TODAY + timedelta(days=3650),
    )

    verdict = evaluate_live_lease(db, application)

    assert verdict.compliant is True
    assert verdict.code == LEASE_VALID
    assert verdict.remaining_lease_years == pytest.approx(3650 / DAYS_PER_YEAR, abs=1e-3)
    assert verdict.required_years == 4.0


def test_short_lease_blocks_the_scrutiny_exit(make_application, make_lease, db):
    application = make_application(application_type=ApplicationType.NEW, duration=4.0)
    make_lease(
        application,
        start=TODAY - timedelta(days=1825),
        end=TODAY + timedelta(days=730),  # ~2 years left, 4 required
    )

    with pytest.raises(LeaseRuleBlocked) as excinfo:
        WorkflowService(db).transition(
            application, ApplicationStatus.EVC, actor="officer@aicte.gov.in"
        )

    assert excinfo.value.verdict.code == LEASE_TOO_SHORT
    assert excinfo.value.http_status == 422

    db.refresh(application)
    assert application.status is ApplicationStatus.SCRUTINY

    entries = AuditService(db).timeline(application.id)
    assert entries[-1].action == "lease_rule.blocked"
    assert entries[-1].payload["verdict"]["code"] == LEASE_TOO_SHORT
    assert entries[-1].payload["attempted_transition"] == "evc"
    assert AuditService(db).verify(application.id).valid


def test_missing_lease_blocks(make_application, db):
    application = make_application()

    with pytest.raises(LeaseRuleBlocked) as excinfo:
        WorkflowService(db).transition(
            application, ApplicationStatus.EVC, actor="officer@aicte.gov.in"
        )

    assert excinfo.value.verdict.code == LEASE_DEED_MISSING
    db.refresh(application)
    assert application.status is ApplicationStatus.SCRUTINY


def test_expired_lease_is_not_live(make_application, make_lease, db):
    application = make_application()
    make_lease(
        application,
        start=TODAY - timedelta(days=3650),
        end=TODAY - timedelta(days=1),
    )

    verdict = evaluate_live_lease(db, application)

    assert verdict.compliant is False
    assert verdict.code == LEASE_EXPIRED
    assert verdict.remaining_lease_years is not None
    assert verdict.remaining_lease_years < 0


def test_lease_starting_in_future_is_not_live(make_application, make_lease, db):
    application = make_application()
    make_lease(
        application,
        start=TODAY + timedelta(days=30),
        end=TODAY + timedelta(days=2000),
    )

    verdict = evaluate_live_lease(db, application)

    assert verdict.compliant is False
    assert verdict.code == LEASE_NOT_COMMENCED


def test_unextracted_lease_is_blocked(make_application, make_lease, db):
    application = make_application()
    make_lease(application, start=None, end=None, extraction_status=ExtractionStatus.PENDING)

    verdict = evaluate_live_lease(db, application)

    assert verdict.compliant is False
    assert verdict.code == LEASE_NOT_EXTRACTED
    assert "pending" in verdict.reason


def test_latest_lease_version_wins(make_application, make_lease, db):
    application = make_application()
    make_lease(application, start=TODAY - timedelta(days=400), end=TODAY + timedelta(days=400))
    make_lease(
        application,
        start=TODAY - timedelta(days=400),
        end=TODAY + timedelta(days=3000),
        version=2,
    )

    verdict = evaluate_live_lease(db, application)

    assert verdict.compliant is True
    assert verdict.lease_end_date == TODAY + timedelta(days=3000)


def test_renewal_skips_evc_but_still_needs_a_live_lease(make_application, make_lease, db):
    application = make_application(application_type=ApplicationType.RENEWAL, duration=2.0)
    make_lease(application, start=TODAY - timedelta(days=1000), end=TODAY + timedelta(days=1500))

    with pytest.raises(InvalidTransition):
        WorkflowService(db).transition(
            application, ApplicationStatus.EVC, actor="officer@aicte.gov.in"
        )

    result = WorkflowService(db).transition(
        application,
        ApplicationStatus.SAC,
        actor="officer@aicte.gov.in",
        remarks="Renewal with valid 4-year lease.",
    )
    assert result.to_status is ApplicationStatus.SAC
    assert result.lease_verdict is not None and result.lease_verdict.compliant


def test_rule_one_only_gates_the_scrutiny_stage(make_application, make_lease, db):
    """Once past Scrutiny the lease gate does not re-fire (documented scope)."""
    application = make_application(status=ApplicationStatus.EVC, duration=4.0)
    make_lease(application, start=TODAY - timedelta(days=1825), end=TODAY + timedelta(days=100))

    result = WorkflowService(db).transition(
        application, ApplicationStatus.SAC, actor="officer@aicte.gov.in"
    )

    assert result.to_status is ApplicationStatus.SAC
    assert result.lease_verdict is None
