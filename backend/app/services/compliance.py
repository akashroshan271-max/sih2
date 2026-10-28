"""Rule 1 — the "Live Lease" check (APH 2024-27, Clause 2.1.e).

An institution's land lease must remain valid for at least the statutory
maximum duration of the longest course it seeks approval for. The remaining
lease term is measured from the evaluation date (scrutiny date) to
``Document.lease_end_date`` of the latest Lease Deed version.

The rule is enforced *before* an application may leave ``Scrutiny``; there is
deliberately no override flag.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Application, Document, DocumentType

#: Gregorian year length; keeps fractional-year maths defensible in an audit.
DAYS_PER_YEAR: float = 365.2425

LEASE_VALID = "lease_valid"
LEASE_DEED_MISSING = "lease_deed_missing"
LEASE_NOT_EXTRACTED = "lease_not_extracted"
LEASE_NOT_COMMENCED = "lease_not_commenced"
LEASE_EXPIRED = "lease_expired"
LEASE_TOO_SHORT = "lease_too_short"


@dataclass(frozen=True)
class LeaseVerdict:
    """Deterministic, auditable outcome of the live-lease rule."""

    code: str
    compliant: bool
    reason: str
    required_years: float
    remaining_lease_years: float | None
    lease_document_id: uuid.UUID | None
    lease_start_date: date | None
    lease_end_date: date | None
    as_of: date

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "compliant": self.compliant,
            "reason": self.reason,
            "required_years": self.required_years,
            "remaining_lease_years": self.remaining_lease_years,
            "lease_document_id": str(self.lease_document_id) if self.lease_document_id else None,
            "lease_start_date": self.lease_start_date.isoformat() if self.lease_start_date else None,
            "lease_end_date": self.lease_end_date.isoformat() if self.lease_end_date else None,
            "as_of": self.as_of.isoformat(),
        }


def latest_lease_deed(db: Session, application_id: uuid.UUID) -> Document | None:
    """Highest-version Lease Deed for an application (re-uploads supersede)."""
    stmt = (
        select(Document)
        .where(
            Document.application_id == application_id,
            Document.doc_type == DocumentType.LEASE_DEED,
        )
        .order_by(Document.version.desc(), Document.uploaded_at.desc())
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none()


def evaluate_live_lease(
    db: Session,
    application: Application,
    *,
    as_of: date | None = None,
) -> LeaseVerdict:
    """Evaluate Clause 2.1.e for ``application`` as of ``as_of`` (default today)."""
    evaluated_on = as_of or date.today()
    required_years = float(application.max_course_duration_years)
    lease = latest_lease_deed(db, application.id)

    def verdict(
        code: str,
        compliant: bool,
        reason: str,
        *,
        remaining: float | None = None,
    ) -> LeaseVerdict:
        return LeaseVerdict(
            code=code,
            compliant=compliant,
            reason=reason,
            required_years=required_years,
            remaining_lease_years=None if remaining is None else round(remaining, 3),
            lease_document_id=lease.id if lease else None,
            lease_start_date=lease.lease_start_date if lease else None,
            lease_end_date=lease.lease_end_date if lease else None,
            as_of=evaluated_on,
        )

    if lease is None:
        return verdict(
            LEASE_DEED_MISSING,
            False,
            "No registered lease deed is on file, so the remaining lease term "
            "cannot be established (APH 2024-27, Cl. 2.1.e).",
        )

    if lease.lease_start_date is None or lease.lease_end_date is None:
        return verdict(
            LEASE_NOT_EXTRACTED,
            False,
            "The lease deed has no machine-readable lease window yet "
            f"(extraction status: {lease.extraction_status.value}). "
            "Re-run extraction or enter the lease dates manually.",
        )

    if lease.lease_start_date > evaluated_on:
        return verdict(
            LEASE_NOT_COMMENCED,
            False,
            f"The lease commences on {lease.lease_start_date.isoformat()}, after the "
            "evaluation date; it is not a live lease.",
        )

    remaining_years = (lease.lease_end_date - evaluated_on).days / DAYS_PER_YEAR

    if lease.lease_end_date <= evaluated_on:
        return verdict(
            LEASE_EXPIRED,
            False,
            f"The lease expired on {lease.lease_end_date.isoformat()} (APH 2024-27, Cl. 2.1.e).",
            remaining=remaining_years,
        )

    if remaining_years < required_years:
        return verdict(
            LEASE_TOO_SHORT,
            False,
            f"Remaining lease term is {remaining_years:.2f} years but the longest "
            f"course applied for runs {required_years:.1f} years (APH 2024-27, "
            "Cl. 2.1.e).",
            remaining=remaining_years,
        )

    return verdict(
        LEASE_VALID,
        True,
        f"Live lease valid until {lease.lease_end_date.isoformat()}: "
        f"{remaining_years:.2f} years remaining against {required_years:.1f} years required.",
        remaining=remaining_years,
    )
