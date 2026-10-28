"""Background tasks: SLA escalation sweep + lease-deed extraction."""

from __future__ import annotations

import uuid
from typing import Any

from app.db.session import session_scope
from app.models import Document, ExtractionStatus
from app.services.gemini import extract_document
from app.services.sla import SlaService
from app.workers.celery_app import celery


@celery.task(name="sla.sweep")
def sweep_sla_dwell() -> dict[str, Any]:
    """Escalate every active docket past its dwell threshold (idempotent)."""
    db = session_scope()
    try:
        result = SlaService(db).scan(actor="system:celery", actor_role="system")
        return {
            "checked": result.checked,
            "overdue": result.overdue,
            "escalated": len(result.escalated),
            "levels": result.levels,
            "scanned_at": result.scanned_at.isoformat(),
        }
    finally:
        db.close()


@celery.task(name="documents.extract")
def extract_document_task(document_id: str) -> dict[str, Any]:
    """Run Gemini extraction for an uploaded lease deed."""
    db = session_scope()
    try:
        document = db.get(Document, uuid.UUID(document_id))
        if document is None:
            return {"status": "missing", "document_id": document_id}

        try:
            extract_document(db, document, actor="system:celery")
        except Exception as exc:  # noqa: BLE001 - row is already marked FAILED
            return {
                "status": ExtractionStatus.FAILED.value,
                "document_id": document_id,
                "error": str(exc),
            }

        return {
            "status": document.extraction_status.value,
            "document_id": document_id,
            "issues": document.extraction_error,
        }
    finally:
        db.close()
