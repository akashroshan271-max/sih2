"""
VERIFLOW-AICTE · SQLAlchemy 2.0 ORM models
=========================================
Canonical schema for the AICTE Approval Process Handbook (APH 2024-27) workflow.

Design notes
------------
* UUID primary keys — safe for offline seeding, imports and cross-service refs.
* Every FK is ``ON DELETE RESTRICT`` except documents: an Application (and its
  audit trail) is a statutory record and must never be hard-deleted.
* ``Application.stage_entry_timestamp`` is the SLA anchor for Rule 3; it is
  re-stamped by the workflow service on every stage transition.
* ``Application.max_course_duration_years`` + ``Document.lease_end_date`` make
  Rule 1 (APH Cl. 2.1.e) evaluable in a single indexed SQL predicate.
* ``AuditLog`` is append-only and tamper-evident: each row stores
  ``sha256_hash = SHA256(canonical_payload || previous_hash)``.
"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime, timedelta
from typing import Any, Final

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.core.time import as_utc, utcnow

# Portable JSON: JSONB on PostgreSQL, plain JSON on SQLite (unit tests).
JSONType = JSON().with_variant(JSONB(), "postgresql")

#: APH 2024-27 — a file may not dwell in one stage beyond this many days.
SLA_THRESHOLD_DAYS: Final[int] = 15


def _pg_enum(enum_cls: type[enum.Enum], name: str) -> SAEnum:
    """Native PG enum storing member *values* (not Python member names)."""
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=True,
        validate_strings=True,
        values_callable=lambda e: [member.value for member in e],
    )


class Base(DeclarativeBase):
    """Declarative base — Alembic autogenerate targets ``Base.metadata``."""


class UTCDateTime(TypeDecorator[datetime]):
    """``TIMESTAMPTZ`` that round-trips as timezone-aware UTC on every backend.

    SQLite (unit tests, local demo) drops ``tzinfo``, which would leak naive
    timestamps into API responses and make the JS client read them as local
    time. Coercing on bind and result keeps the contract identical to
    PostgreSQL: every datetime leaving the ORM is UTC-aware.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: object) -> datetime | None:
        return None if value is None else as_utc(value)

    def process_result_value(self, value: datetime | None, dialect: object) -> datetime | None:
        return None if value is None else as_utc(value)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


# =============================================================================
# Enumerations
# =============================================================================


class InstitutionType(str, enum.Enum):
    """Programme family regulated under the APH."""

    ENGINEERING = "engineering"
    POLYTECHNIC = "polytechnic"
    PHARMACY = "pharmacy"
    ARCHITECTURE = "architecture"
    MANAGEMENT = "management"
    HOTEL_MANAGEMENT = "hotel_management"
    APPLIED_ARTS = "applied_arts"


class ProgrammeLevel(str, enum.Enum):
    """Drives the statutory maximum course duration used by Rule 1."""

    DIPLOMA = "diploma"
    UG = "ug"
    PG = "pg"
    INTEGRATED = "integrated"


class ApplicationType(str, enum.Enum):
    """Determines triage routing (Rule 2): NEW / EXPANSION require an EVC visit."""

    NEW = "new"
    EXPANSION = "expansion"
    RENEWAL = "renewal"
    CLOSURE = "closure"


class ApplicationStatus(str, enum.Enum):
    """Linear state machine: SCRUTINY → EVC → SAC|SHC → APPROVED|REJECTED."""

    SCRUTINY = "scrutiny"
    EVC = "evc"
    SAC = "sac"
    SHC = "shc"
    APPROVED = "approved"
    REJECTED = "rejected"


#: Stages that carry an SLA clock (terminal states do not).
ACTIVE_STAGES: Final[frozenset[ApplicationStatus]] = frozenset(
    {
        ApplicationStatus.SCRUTINY,
        ApplicationStatus.EVC,
        ApplicationStatus.SAC,
        ApplicationStatus.SHC,
    }
)


class OfficerRole(str, enum.Enum):
    """The statutory desk an officer signs in to.

    Each desk owns exactly one workflow stage. A signed-in officer may only see
    the dockets currently sitting at their desk and may only perform the moves
    that stage is statutorily competent to make. The Regional Officer is the
    oversight authority: read access across every stage plus the SLA sweep.
    """

    SCRUTINY_OFFICER = "scrutiny_officer"
    EVC_MEMBER = "evc_member"
    SAC_MEMBER = "sac_member"
    SHC_MEMBER = "shc_member"
    REGIONAL_OFFICER = "regional_officer"


class DocumentType(str, enum.Enum):
    LEASE_DEED = "lease_deed"
    FIRE_NOC = "fire_noc"
    LAND_RECORD = "land_record"
    BUILDING_PLAN = "building_plan"
    AFFILIATION_CERTIFICATE = "affiliation_certificate"
    FACULTY_LIST = "faculty_list"
    FINANCIAL_STATEMENT = "financial_statement"
    OTHER = "other"


class ExtractionStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    EXTRACTED = "extracted"
    NEEDS_REVIEW = "needs_review"
    FAILED = "failed"


# =============================================================================
# 0. Officer  (authenticated identity + desk assignment)
# =============================================================================


class Officer(Base, TimestampMixin):
    """A signed-in officer and the desk they are entitled to work.

    Deliberately not an applicant account: institutions file through the portal
    (service-to-service), while decisions are made by named officers whose role
    is stamped onto every audit entry they sign.
    """

    __tablename__ = "officers"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(160), nullable=False, unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    designation: Mapped[str] = mapped_column(String(140), nullable=False)
    role: Mapped[OfficerRole] = mapped_column(
        _pg_enum(OfficerRole, "officer_role"), nullable=False, index=True
    )
    #: Jurisdiction for the Regional Officer (audit/oversight context).
    region_state: Mapped[str | None] = mapped_column(String(64))

    #: bcrypt digest; never the password itself.
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    last_login_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    __table_args__ = (Index("ix_officers_role_active", "role", "is_active"),)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Officer {self.email} {self.role.value}>"


# =============================================================================
# 1. Institution
# =============================================================================


class Institution(Base, TimestampMixin):
    __tablename__ = "institutions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)

    # AICTE Permanent ID (e.g. "1-12345678") — the regulator's master key.
    aicte_permanent_id: Mapped[str] = mapped_column(
        String(32), nullable=False, unique=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    district: Mapped[str | None] = mapped_column(String(64))

    institution_type: Mapped[InstitutionType] = mapped_column(
        _pg_enum(InstitutionType, "institution_type"), nullable=False
    )
    approved_intake: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    is_autonomous: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )

    applications: Mapped[list[Application]] = relationship(
        back_populates="institution", order_by="Application.created_at.desc()"
    )

    __table_args__ = (
        CheckConstraint("approved_intake >= 0", name="ck_institutions_intake_non_negative"),
        Index("ix_institutions_state_type", "state", "institution_type"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Institution {self.aicte_permanent_id} {self.name!r}>"


# =============================================================================
# 2. Application
# =============================================================================


class Application(Base, TimestampMixin):
    __tablename__ = "applications"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)

    # Human-facing docket number, e.g. "AICTE/ER/2026-27/000123".
    application_number: Mapped[str] = mapped_column(
        String(48), nullable=False, unique=True, index=True
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("institutions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    academic_year: Mapped[str] = mapped_column(String(9), nullable=False)  # "2026-27"

    application_type: Mapped[ApplicationType] = mapped_column(
        _pg_enum(ApplicationType, "application_type"), nullable=False
    )
    programme_level: Mapped[ProgrammeLevel] = mapped_column(
        _pg_enum(ProgrammeLevel, "programme_level"), nullable=False
    )
    #: Statutory maximum duration of the longest course applied for (Rule 1 input).
    max_course_duration_years: Mapped[float] = mapped_column(
        Numeric(3, 1, asdecimal=False),
        nullable=False,
        default=4.0,
        server_default=text("4.0"),
    )

    #: Current workflow state (Rule 2). Indexed for the Kanban + SLA sweep.
    status: Mapped[ApplicationStatus] = mapped_column(
        _pg_enum(ApplicationStatus, "application_status"),
        nullable=False,
        default=ApplicationStatus.SCRUTINY,
        server_default=ApplicationStatus.SCRUTINY.value,
    )
    #: SLA anchor — rewritten on every transition (Rule 3).
    stage_entry_timestamp: Mapped[datetime] = mapped_column(
        UTCDateTime, nullable=False, server_default=func.now()
    )

    submitted_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    decided_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    decision_remarks: Mapped[str | None] = mapped_column(Text)

    #: Intake sought by this application (delta for EXPANSION, target for NEW).
    proposed_intake: Mapped[int | None] = mapped_column(Integer)

    documents: Mapped[list[Document]] = relationship(
        back_populates="application",
        cascade="all, delete-orphan",
        order_by="Document.uploaded_at",
    )
    audit_logs: Mapped[list[AuditLog]] = relationship(
        back_populates="application", order_by="AuditLog.timestamp"
    )
    institution: Mapped[Institution] = relationship(back_populates="applications")

    __table_args__ = (
        # One docket per institution / year / type / level: a college may file a
        # NEW-UG and a NEW-Diploma docket in the same cycle, but not two NEW-UGs.
        UniqueConstraint(
            "institution_id",
            "academic_year",
            "application_type",
            "programme_level",
            name="uq_applications_inst_year_type_level",
        ),
        CheckConstraint(
            "proposed_intake IS NULL OR proposed_intake >= 0",
            name="ck_applications_proposed_intake_non_negative",
        ),
        CheckConstraint(
            "max_course_duration_years > 0",
            name="ck_applications_max_duration_positive",
        ),
        # Dwell-time sweep: WHERE status IN (active) AND stage_entry_timestamp < now() - 15d
        Index("ix_applications_status_stage_entry", "status", "stage_entry_timestamp"),
    )

    # --- Derived (read-only) SLA helpers -----------------------------------
    @property
    def sla_due_at(self) -> datetime:
        return as_utc(self.stage_entry_timestamp) + timedelta(days=SLA_THRESHOLD_DAYS)

    @property
    def dwell_days(self) -> float:
        """Days spent in the current stage (Rule 3 escalation input)."""
        entered = as_utc(self.stage_entry_timestamp)
        return (utcnow() - entered).total_seconds() / 86_400

    @property
    def is_sla_breached(self) -> bool:
        return self.status in ACTIVE_STAGES and self.dwell_days > SLA_THRESHOLD_DAYS

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Application {self.application_number} {self.status.value}>"


# =============================================================================
# 3. Document
# =============================================================================


class Document(Base, TimestampMixin):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )

    doc_type: Mapped[DocumentType] = mapped_column(
        _pg_enum(DocumentType, "document_type"), nullable=False
    )
    #: Re-uploads supersede earlier versions; highest version is authoritative.
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default=text("1"))

    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    s3_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(128))
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    content_sha256: Mapped[str | None] = mapped_column(String(64))
    uploaded_at: Mapped[datetime] = mapped_column(
        UTCDateTime, nullable=False, server_default=func.now()
    )
    uploaded_by: Mapped[str | None] = mapped_column(String(128))

    # --- Gemini extraction output ------------------------------------------
    extraction_status: Mapped[ExtractionStatus] = mapped_column(
        _pg_enum(ExtractionStatus, "extraction_status"),
        nullable=False,
        default=ExtractionStatus.PENDING,
        server_default=ExtractionStatus.PENDING.value,
    )
    #: Raw, strictly-typed JSON returned by gemini-3.6-flash (audit trail).
    extracted_json_data: Mapped[dict[str, Any] | None] = mapped_column(JSONType)
    #: Normalised projection of the extraction so Rule 1 is a plain SQL check.
    lease_start_date: Mapped[date | None] = mapped_column(Date)
    lease_end_date: Mapped[date | None] = mapped_column(Date)
    total_land_area_sqm: Mapped[float | None] = mapped_column(Numeric(12, 2, asdecimal=False))
    survey_numbers: Mapped[list[str] | None] = mapped_column(JSONType)
    extraction_confidence: Mapped[float | None] = mapped_column(
        Numeric(4, 3, asdecimal=False)
    )
    extraction_model: Mapped[str | None] = mapped_column(String(64))
    extracted_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    extraction_error: Mapped[str | None] = mapped_column(Text)

    application: Mapped[Application] = relationship(back_populates="documents")

    __table_args__ = (
        UniqueConstraint(
            "application_id", "doc_type", "version", name="uq_documents_app_type_version"
        ),
        CheckConstraint(
            "lease_end_date IS NULL OR lease_start_date IS NULL "
            "OR lease_end_date > lease_start_date",
            name="ck_documents_lease_window_valid",
        ),
        CheckConstraint("version >= 1", name="ck_documents_version_positive"),
        # "Latest live lease for this application" lookup.
        Index("ix_documents_app_type_version", "application_id", "doc_type", "version"),
        Index("ix_documents_lease_end", "lease_end_date"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Document {self.doc_type.value} v{self.version} app={self.application_id}>"


# =============================================================================
# 4. AuditLog  (append-only, SHA-256 hash chained)
# =============================================================================


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("applications.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    #: Dotted action code, e.g. "stage.transition", "lease_rule.blocked",
    #: "sla.escalation.L1", "document.extracted".
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    actor: Mapped[str] = mapped_column(String(128), nullable=False)  # officer id / "system:celery"
    actor_role: Mapped[str | None] = mapped_column(String(64))

    from_status: Mapped[ApplicationStatus | None] = mapped_column(
        _pg_enum(ApplicationStatus, "application_status")
    )
    to_status: Mapped[ApplicationStatus | None] = mapped_column(
        _pg_enum(ApplicationStatus, "application_status")
    )

    #: Structured evidence: rule inputs/outputs, extracted JSON, remarks.
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONType)

    timestamp: Mapped[datetime] = mapped_column(
        UTCDateTime, nullable=False, server_default=func.now()
    )

    # --- Integrity chain ---------------------------------------------------
    #: SHA256(previous_hash || canonical_json(core_fields)); hex digest.
    sha256_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    #: Hash of the preceding log entry for this application (NULL for genesis).
    previous_hash: Mapped[str | None] = mapped_column(String(64))

    application: Mapped[Application] = relationship(back_populates="audit_logs")

    __table_args__ = (
        Index("ix_audit_logs_application_timestamp", "application_id", "timestamp"),
        CheckConstraint("length(sha256_hash) = 64", name="ck_audit_logs_hash_length"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AuditLog {self.action} app={self.application_id} {self.timestamp}>"
