"""Append-only audit trail with SHA-256 hash chaining.

The service is the only writer of :class:`~app.models.AuditLog`; API routes and
Celery tasks must go through it so every entry is linked into the chain.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.integrity import (
    ChainVerification,
    compute_audit_hash,
    verify_chain,
)
from app.core.time import utcnow
from app.models import Application, ApplicationStatus, AuditLog


class AuditService:
    """Writes tamper-evident history for one application at a time."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Write path
    # ------------------------------------------------------------------
    def record(
        self,
        *,
        application: Application,
        action: str,
        actor: str,
        actor_role: str | None = None,
        from_status: ApplicationStatus | None = None,
        to_status: ApplicationStatus | None = None,
        payload: dict[str, Any] | None = None,
        occurred_at: datetime | None = None,
        commit: bool = False,
    ) -> AuditLog:
        """Append an entry, chaining it to the application's latest digest.

        ``commit=False`` lets the caller finish its transaction (workflow keeps
        the status change and its audit entry atomic).
        """
        if application.id is None:
            raise ValueError("Audit entries require a persisted application")

        timestamp = occurred_at or utcnow()
        self._lock_chain(application.id)
        previous_hash = self._last_hash(application.id)

        entry = AuditLog(
            application_id=application.id,
            action=action,
            actor=actor,
            actor_role=actor_role,
            from_status=from_status,
            to_status=to_status,
            payload=payload,
            timestamp=timestamp,
            previous_hash=previous_hash,
            sha256_hash=compute_audit_hash(
                application_id=application.id,
                action=action,
                actor=actor,
                timestamp=timestamp,
                from_status=from_status,
                to_status=to_status,
                payload=payload,
                previous_hash=previous_hash,
            ),
        )
        self.db.add(entry)
        self.db.flush()
        if commit:
            self.db.commit()
        return entry

    # ------------------------------------------------------------------
    # Read path
    # ------------------------------------------------------------------
    def timeline(self, application_id: uuid.UUID, *, limit: int = 100) -> list[AuditLog]:
        stmt = (
            select(AuditLog)
            .where(AuditLog.application_id == application_id)
            .order_by(AuditLog.timestamp.asc(), AuditLog.id.asc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def verify(self, application_id: uuid.UUID) -> ChainVerification:
        return verify_chain(self.timeline(application_id, limit=10_000))

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _last_hash(self, application_id: uuid.UUID) -> str | None:
        stmt = (
            select(AuditLog.sha256_hash)
            .where(AuditLog.application_id == application_id)
            .order_by(AuditLog.timestamp.desc(), AuditLog.id.desc())
            .limit(1)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def _lock_chain(self, application_id: uuid.UUID) -> None:
        """Serialise appends for one application (PostgreSQL only).

        A transaction-scoped advisory lock prevents two officers (or an officer
        and the SLA sweeper) from reading the same chain head and forking it.
        SQLite has no advisory locks and runs single-writer anyway.
        """
        bind = self.db.get_bind()
        if bind is not None and bind.dialect.name == "postgresql":
            self.db.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
                {"key": f"audit:{application_id}"},
            )
