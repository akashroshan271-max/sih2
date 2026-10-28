"""SHA-256 audit chain: construction, determinism and tamper detection."""

from __future__ import annotations

from datetime import timedelta

from app.core.integrity import compute_audit_hash
from app.core.time import utcnow
from app.models import ApplicationStatus
from app.services.audit import AuditService


def _seed_chain(db, application, count: int = 3):
    service = AuditService(db)
    base = utcnow() - timedelta(days=count)
    entries = []
    for index in range(count):
        entries.append(
            service.record(
                application=application,
                action=f"test.action.{index}",
                actor="officer@aicte.gov.in",
                actor_role="officer",
                from_status=ApplicationStatus.SCRUTINY,
                to_status=ApplicationStatus.EVC if index else None,
                payload={"index": index},
                occurred_at=base + timedelta(days=index),
            )
        )
    db.commit()
    return entries


def test_chain_links_and_verifies(make_application, db):
    application = make_application()
    entries = _seed_chain(db, application, 3)

    assert entries[0].previous_hash is None
    assert entries[1].previous_hash == entries[0].sha256_hash
    assert entries[2].previous_hash == entries[1].sha256_hash
    assert len({entry.sha256_hash for entry in entries}) == 3
    assert all(len(entry.sha256_hash) == 64 for entry in entries)

    verification = AuditService(db).verify(application.id)
    assert verification.valid is True
    assert verification.checked == 3
    assert verification.broken_at is None


def test_hash_is_reproducible(make_application, db):
    application = make_application()
    entry = _seed_chain(db, application, 1)[0]

    recomputed = compute_audit_hash(
        application_id=entry.application_id,
        action=entry.action,
        actor=entry.actor,
        timestamp=entry.timestamp,
        from_status=entry.from_status,
        to_status=entry.to_status,
        payload=entry.payload,
        previous_hash=entry.previous_hash,
    )
    assert recomputed == entry.sha256_hash


def test_tampered_payload_is_detected(make_application, db):
    application = make_application()
    entries = _seed_chain(db, application, 3)

    entries[1].payload = {"index": 999, "forged": True}
    db.commit()

    verification = AuditService(db).verify(application.id)
    assert verification.valid is False
    assert verification.broken_at == 1
    assert "sha256_hash does not match" in verification.reason


def test_deleted_entry_breaks_the_chain(make_application, db):
    application = make_application()
    entries = _seed_chain(db, application, 3)

    db.delete(entries[1])
    db.commit()

    verification = AuditService(db).verify(application.id)
    assert verification.valid is False
    assert verification.broken_at == 1
    assert "previous_hash" in verification.reason


def test_tampered_hash_is_detected(make_application, db):
    application = make_application()
    entries = _seed_chain(db, application, 2)

    entries[0].sha256_hash = "f" * 64
    db.commit()

    verification = AuditService(db).verify(application.id)
    assert verification.valid is False
    assert verification.broken_at == 0
