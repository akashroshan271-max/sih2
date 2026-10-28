"""Document endpoints: fetch metadata and run lease-deed extraction."""

from __future__ import annotations

import uuid

from fastapi import APIRouter
from sqlalchemy.orm import Session

from app.api.deps import CurrentActor, DbSession
from app.models import Application, Document
from app.schemas.application import DocumentExtractionResponse, LeaseVerdictRead
from app.schemas.document import DocumentRead
from app.services.compliance import evaluate_live_lease
from app.services.errors import NotFoundError
from app.services.gemini import extract_document
from app.services.permissions import ensure_can_upload, ensure_can_view

router = APIRouter(prefix="/documents", tags=["documents"])


def _load_document(db: Session, document_id: uuid.UUID) -> Document:
    document = db.get(Document, document_id)
    if document is None:
        raise NotFoundError(f"Document {document_id} was not found.")
    return document


@router.get("/{document_id}", response_model=DocumentRead)
def get_document(
    document_id: uuid.UUID, db: DbSession, actor: CurrentActor
) -> DocumentRead:
    document = _load_document(db, document_id)
    application = db.get(Application, document.application_id)
    if application is None:  # pragma: no cover - FK is RESTRICT/CASCADE
        raise NotFoundError("The parent application was not found.")
    ensure_can_view(actor.role_enum, application)
    return DocumentRead.model_validate(document)


@router.post("/{document_id}/extract", response_model=DocumentExtractionResponse)
def extract_lease_deed(
    document_id: uuid.UUID,
    db: DbSession,
    actor: CurrentActor,
) -> DocumentExtractionResponse:
    """Run Gemini OCR synchronously and return the updated document.

    A partial extraction is persisted as ``NEEDS_REVIEW``; a hard failure is
    persisted as ``FAILED`` with the reason on the row, so the officer can retry
    without losing the upload.
    """
    document = _load_document(db, document_id)
    parent = db.get(Application, document.application_id)
    if parent is None:  # pragma: no cover
        raise NotFoundError("The parent application was not found.")
    ensure_can_upload(actor.role_enum, parent)
    extract_document(db, document, actor=actor.id, actor_role=actor.role)

    application = db.get(Application, document.application_id)
    verdict = (
        LeaseVerdictRead.model_validate(evaluate_live_lease(db, application))
        if application is not None
        else None
    )
    return DocumentExtractionResponse(
        document=DocumentRead.model_validate(document),
        lease_verdict=verdict,
    )
