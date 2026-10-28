"""Role-scoped workspace construction.

Each phase officer gets a desk view containing only the dockets at their stage,
the facts their stage must verify, and the moves their desk may make. The
Regional Officer gets the oversight variant: every active docket, read-only,
with the SLA register.

The AI is not consulted here. Extracted lease data appears as *evidence* with
its extraction status, and every action label is a statutory move an officer has
to sign.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.core.time import utcnow
from app.models import (
    ACTIVE_STAGES,
    Application,
    ApplicationStatus,
    ApplicationType,
    AuditLog,
    Document,
    DocumentType,
    ExtractionStatus,
    Officer,
    OfficerRole,
)
from app.schemas.auth import OfficerRead
from app.schemas.dashboard import SlaAlertRead
from app.schemas.workspace import (
    DeskRead,
    LeaseSnapshotRead,
    WorkspaceActionRead,
    WorkspaceActivityRead,
    WorkspaceDocketRead,
    WorkspaceDocumentRead,
    WorkspaceFactRead,
    WorkspaceKpiRead,
    WorkspaceResponse,
)
from app.services import analytics
from app.services.compliance import LeaseVerdict, evaluate_live_lease
from app.services.permissions import (
    permitted_transitions,
    stage_for_role,
)
from app.services.sla import SlaService

QUEUE_LIMIT = 60
ESCALATION_LIMIT = 12

EXTRACTION_LABEL: dict[ExtractionStatus, str] = {
    ExtractionStatus.PENDING: "not yet read",
    ExtractionStatus.PROCESSING: "reading",
    ExtractionStatus.EXTRACTED: "machine-read",
    ExtractionStatus.NEEDS_REVIEW: "needs review",
    ExtractionStatus.FAILED: "read failed",
}

ACTION_LABEL: dict[ApplicationStatus, str] = {
    ApplicationStatus.SCRUTINY: "Return to scrutiny",
    ApplicationStatus.EVC: "Send to EVC",
    ApplicationStatus.SAC: "Send to SAC",
    ApplicationStatus.SHC: "Send to SHC",
    ApplicationStatus.APPROVED: "Approve docket",
    ApplicationStatus.REJECTED: "Reject docket",
}

STAGE_LABEL: dict[ApplicationStatus, str] = {
    ApplicationStatus.SCRUTINY: "Scrutiny",
    ApplicationStatus.EVC: "Expert Visit Committee",
    ApplicationStatus.SAC: "Standing Approval Committee",
    ApplicationStatus.SHC: "Standing Hearing Committee",
    ApplicationStatus.APPROVED: "Approved",
    ApplicationStatus.REJECTED: "Rejected",
}


@dataclass(frozen=True)
class DeskProfile:
    label: str
    mandate: str
    checklist: tuple[str, ...]
    next_step: str
    authority: str
    notice: str


DESKS: dict[OfficerRole, DeskProfile] = {
    OfficerRole.SCRUTINY_OFFICER: DeskProfile(
        label="Scrutiny desk",
        mandate=(
            "Verify the statutory evidence for every file before it leaves "
            "scrutiny. This desk is the Rule 1 gatekeeper: the registered lease "
            "must stay live for at least the maximum course duration."
        ),
        checklist=(
            "Registered lease deed is on file and its dates have been read",
            "Remaining lease ≥ maximum course duration (APH Cl. 2.1.e)",
            "Land area and survey numbers match the application",
            "All required evidence is uploaded and legible",
        ),
        next_step=(
            "Forward to EVC for a new or expanding programme, or straight to SAC "
            "for a renewal or closure."
        ),
        authority="Forward or reject with a recorded reason. Cannot approve.",
        notice=(
            "Only dockets at Scrutiny appear here. Forwarding one re-runs the "
            "live-lease rule; a failing lease is blocked with its verdict."
        ),
    ),
    OfficerRole.EVC_MEMBER: DeskProfile(
        label="Expert Visit Committee",
        mandate=(
            "Assess the physical and academic readiness of the institution on "
            "site and record the committee's finding for the SAC."
        ),
        checklist=(
            "Land area and survey numbers support the proposed intake",
            "Building plan and fire NOC are in order",
            "Faculty strength and infrastructure match the programme",
            "Scrutiny observations have been answered",
        ),
        next_step="Recommend the file to SAC, or refer it to SHC for a hearing.",
        authority="Recommends the route. Cannot approve.",
        notice=(
            "Only dockets currently with the Expert Visit Committee appear here, "
            "with the evidence and scrutiny note needed for the visit."
        ),
    ),
    OfficerRole.SAC_MEMBER: DeskProfile(
        label="Standing Approval Committee",
        mandate=(
            "Review the whole file and the findings of scrutiny and the expert "
            "visit, then decide the approval for the academic year."
        ),
        checklist=(
            "Every prior stage has recorded its finding",
            "Intake sought is supported by land and infrastructure",
            "Lease covers the full course duration",
            "Conditions, if any, are written into the decision note",
        ),
        next_step="Approve, reject with reasons, or refer to SHC.",
        authority="Decides at SAC: approve or reject, with the reason on record.",
        notice=(
            "Only dockets at SAC appear here. The decision you record is signed "
            "into the audit chain under your officer ID."
        ),
    ),
    OfficerRole.SHC_MEMBER: DeskProfile(
        label="Standing Hearing Committee",
        mandate=(
            "Hear the matter referred by the SAC and decide it on the record, "
            "including any representation from the institution."
        ),
        checklist=(
            "The referral ground from SAC is on record",
            "The institution's representation has been heard",
            "Prior-stage findings and the lease verdict are before the committee",
            "The decision note states the reasoning",
        ),
        next_step="Approve or reject on the record.",
        authority="Decides at SHC: approve or reject, with the reasoning recorded.",
        notice=(
            "Only dockets referred to the Standing Hearing Committee appear here."
        ),
    ),
    OfficerRole.REGIONAL_OFFICER: DeskProfile(
        label="Regional oversight",
        mandate=(
            "Supervise every desk in the region, watch dwell-time breaches and "
            "verify that the audit chain has not been altered."
        ),
        checklist=(
            "No docket is dwelling past the 15-day threshold",
            "Each desk is recording its own findings",
            "Lease warnings are being cleared, not ignored",
            "Audit chains verify after every decision",
        ),
        next_step=(
            "Run the SLA sweep, open any docket read-only, and verify its audit "
            "chain before the approval letter issues."
        ),
        authority=(
            "Oversight and delegated action; the owning desk records the statutory "
            "finding."
        ),
        notice=(
            "Oversight desk: every active docket is visible. Decisions are signed "
            "by the desk that owns the stage."
        ),
    ),
}


def _fmt_date(value: date | None) -> str:
    return value.strftime("%d %b %Y") if value else "—"


def _fmt_seats(value: int | None) -> str:
    return f"{value:,} seats" if value is not None else "—"


def _latest(application: Application, doc_type: DocumentType) -> Document | None:
    versions = [doc for doc in application.documents if doc.doc_type is doc_type]
    return max(versions, key=lambda doc: doc.version) if versions else None


def _lease_snapshot(
    db: Session, application: Application
) -> tuple[LeaseSnapshotRead, LeaseVerdict]:
    document = _latest(application, DocumentType.LEASE_DEED)
    verdict = evaluate_live_lease(db, application)
    return (
        LeaseSnapshotRead(
            document_id=document.id if document else None,
            version=document.version if document else None,
            extraction_status=document.extraction_status if document else None,
            lease_start_date=document.lease_start_date if document else None,
            lease_end_date=document.lease_end_date if document else None,
            remaining_years=verdict.remaining_lease_years,
            required_years=verdict.required_years,
            total_land_area_sqm=(
                float(document.total_land_area_sqm)
                if document and document.total_land_area_sqm is not None
                else None
            ),
            survey_numbers=list(document.survey_numbers or []) if document else [],
            verdict_code=verdict.code,
            verdict_reason=verdict.reason,
            compliant=verdict.compliant,
        ),
        verdict,
    )


def _facts(
    role: OfficerRole,
    application: Application,
    lease: LeaseSnapshotRead,
    document_count: int,
    attention_count: int,
    last_activity: WorkspaceActivityRead | None,
) -> list[WorkspaceFactRead]:
    institution = application.institution
    stage = stage_for_role(role)
    route = "EVC required" if application.application_type in (
        ApplicationType.NEW,
        ApplicationType.EXPANSION,
    ) else "EVC waived"
    base: list[WorkspaceFactRead] = [
        WorkspaceFactRead(label="Application type", value=application.application_type.value.title(), note=route),
        WorkspaceFactRead(
            label="Intake sought",
            value=_fmt_seats(application.proposed_intake),
            note=f"approved intake {institution.approved_intake:,}",
        ),
        WorkspaceFactRead(
            label="Maximum course duration",
            value=f"{float(application.max_course_duration_years):.1f} years",
        ),
    ]

    if role is OfficerRole.SCRUTINY_OFFICER:
        return base + [
            WorkspaceFactRead(
                label="Lease window",
                value=f"{_fmt_date(lease.lease_start_date)} → {_fmt_date(lease.lease_end_date)}",
                note=(
                    f"v{lease.version} · {EXTRACTION_LABEL[lease.extraction_status]}"
                    if lease.extraction_status
                    else "no lease deed on file"
                ),
            ),
            WorkspaceFactRead(
                label="Remaining vs required",
                value=(
                    f"{lease.remaining_years:.1f} / {lease.required_years:.1f} years"
                    if lease.remaining_years is not None
                    else f"unknown / {lease.required_years:.1f} years"
                ),
                note="Rule 1 (APH Cl. 2.1.e)",
            ),
            WorkspaceFactRead(
                label="Land evidence",
                value=(
                    f"{lease.total_land_area_sqm:,.0f} m²"
                    if lease.total_land_area_sqm
                    else "not extracted"
                ),
                note=(
                    f"survey {', '.join(lease.survey_numbers)}"
                    if lease.survey_numbers
                    else "no survey numbers read"
                ),
            ),
            WorkspaceFactRead(
                label="Evidence",
                value=f"{document_count} document{'s' if document_count != 1 else ''}",
                note=f"{attention_count} needing attention" if attention_count else "all readable",
            ),
        ]

    if role is OfficerRole.EVC_MEMBER:
        return base + [
            WorkspaceFactRead(
                label="Land available",
                value=(
                    f"{lease.total_land_area_sqm:,.0f} m²"
                    if lease.total_land_area_sqm
                    else "not on record"
                ),
                note=(
                    f"survey {', '.join(lease.survey_numbers)}"
                    if lease.survey_numbers
                    else "survey numbers not read"
                ),
            ),
            WorkspaceFactRead(
                label="Lease cover",
                value=(
                    f"{lease.remaining_years:.1f} years remaining"
                    if lease.remaining_years is not None
                    else "unverified"
                ),
                note=f"{lease.required_years:.1f} years required",
            ),
            WorkspaceFactRead(
                label="Scrutiny note",
                value=last_activity.actor if last_activity else "—",
                note=f"forwarded {_fmt_date(last_activity.timestamp.date())}" if last_activity else None,
            ),
            WorkspaceFactRead(
                label="Evidence",
                value=f"{document_count} document{'s' if document_count != 1 else ''}",
                note=f"{attention_count} needing attention" if attention_count else "all readable",
            ),
        ]

    if role in (OfficerRole.SAC_MEMBER, OfficerRole.SHC_MEMBER):
        cleared = "EVC + scrutiny" if route == "EVC required" else "scrutiny"
        return base + [
            WorkspaceFactRead(
                label="Stages cleared",
                value=cleared,
                note="statutory sequence complete" if stage is ApplicationStatus.SAC else "referred for hearing",
            ),
            WorkspaceFactRead(
                label="Lease cover",
                value=(
                    f"{lease.remaining_years:.1f} years remaining"
                    if lease.remaining_years is not None
                    else "unverified"
                ),
                note=f"{lease.required_years:.1f} years required",
            ),
            WorkspaceFactRead(
                label="Last finding",
                value=last_activity.actor if last_activity else "—",
                note=f"{last_activity.action} · {_fmt_date(last_activity.timestamp.date())}" if last_activity else None,
            ),
            WorkspaceFactRead(
                label="Land evidence",
                value=(
                    f"{lease.total_land_area_sqm:,.0f} m²"
                    if lease.total_land_area_sqm
                    else "not on record"
                ),
                note=(
                    f"survey {', '.join(lease.survey_numbers)}"
                    if lease.survey_numbers
                    else None
                ),
            ),
        ]

    # Oversight: stage, dwell and audit facts.
    return base + [
        WorkspaceFactRead(
            label="Held at",
            value=STAGE_LABEL[application.status],
            note=f"{application.dwell_days:.0f} days dwell",
        ),
        WorkspaceFactRead(
            label="Lease verdict",
            value=lease.verdict_code.replace("_", " "),
            note=lease.verdict_reason,
        ),
        WorkspaceFactRead(
            label="Evidence",
            value=f"{document_count} document{'s' if document_count != 1 else ''}",
            note=(
                f"{EXTRACTION_LABEL[lease.extraction_status]} lease"
                if lease.extraction_status
                else "no lease deed on file"
            ),
        ),
        WorkspaceFactRead(
            label="Last activity",
            value=last_activity.actor if last_activity else "—",
            note=(
                f"{last_activity.action} · {_fmt_date(last_activity.timestamp.date())}"
                if last_activity
                else None
            ),
        ),
    ]


class WorkspaceService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()

    def build(self, officer: Officer) -> WorkspaceResponse:
        profile = DESKS[officer.role]
        stage = stage_for_role(officer.role)
        applications = self._queue(officer.role, stage)
        activities = self._last_activity({app.id for app in applications})

        dockets: list[WorkspaceDocketRead] = []
        leases: list[LeaseSnapshotRead] = []
        attention_total = 0

        for application in applications:
            lease, verdict = _lease_snapshot(self.db, application)
            leases.append(lease)
            documents = [
                WorkspaceDocumentRead(
                    id=document.id,
                    doc_type=document.doc_type,
                    version=document.version,
                    file_name=document.file_name,
                    extraction_status=document.extraction_status,
                    uploaded_at=document.uploaded_at,
                    lease_start_date=document.lease_start_date,
                    lease_end_date=document.lease_end_date,
                    size_bytes=document.size_bytes,
                )
                for document in application.documents
            ]
            attention = sum(
                1
                for document in application.documents
                if document.extraction_status
                in (
                    ExtractionStatus.PENDING,
                    ExtractionStatus.NEEDS_REVIEW,
                    ExtractionStatus.FAILED,
                )
            )
            attention_total += attention
            activity = activities.get(application.id)
            dockets.append(
                WorkspaceDocketRead(
                    id=application.id,
                    application_number=application.application_number,
                    institution_name=application.institution.name,
                    state=application.institution.state,
                    district=application.institution.district,
                    institution_type=application.institution.institution_type,
                    approved_intake=application.institution.approved_intake,
                    academic_year=application.academic_year,
                    application_type=application.application_type,
                    programme_level=application.programme_level,
                    proposed_intake=application.proposed_intake,
                    max_course_duration_years=float(application.max_course_duration_years),
                    status=application.status,
                    stage_entry_timestamp=application.stage_entry_timestamp,
                    dwell_days=application.dwell_days,
                    sla_due_at=application.sla_due_at,
                    is_sla_breached=application.is_sla_breached,
                    submitted_at=application.submitted_at,
                    decided_at=application.decided_at,
                    lease=lease,
                    documents=documents,
                    facts=_facts(
                        officer.role,
                        application,
                        lease,
                        len(documents),
                        attention,
                        activity,
                    ),
                    actions=self._actions(officer.role, application, verdict),
                    last_activity=activity,
                )
            )

        queue_total = self._queue_total(stage)
        alerts = (
            SlaService(self.db).alerts() if officer.role is OfficerRole.REGIONAL_OFFICER else []
        )

        return WorkspaceResponse(
            generated_at=utcnow(),
            officer=OfficerRead.model_validate(officer),
            desk=DeskRead(
                role=officer.role,
                label=profile.label,
                stage=stage,
                stage_label=STAGE_LABEL[stage] if stage else "All stages",
                mandate=profile.mandate,
                checklist=list(profile.checklist),
                next_step=profile.next_step,
                authority=profile.authority,
            ),
            notice=profile.notice,
            kpis=self._kpis(officer.role, dockets, leases, attention_total),
            queue=dockets,
            queue_total=queue_total,
            stage_counts=self._stage_counts(stage),
            escalations=[
                SlaAlertRead.model_validate(alert) for alert in alerts[:ESCALATION_LIMIT]
            ],
        )

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------
    def _queue(self, role: OfficerRole, stage: ApplicationStatus | None) -> list[Application]:
        stmt = (
            select(Application)
            .options(
                selectinload(Application.institution),
                selectinload(Application.documents),
            )
            .order_by(Application.stage_entry_timestamp.asc())
            .limit(QUEUE_LIMIT)
        )
        if stage is not None:
            stmt = stmt.where(Application.status == stage)
        else:
            stmt = stmt.where(Application.status.in_(tuple(ACTIVE_STAGES)))
        return list(self.db.execute(stmt).scalars().all())

    def _queue_total(self, stage: ApplicationStatus | None) -> int:
        stmt = select(func.count()).select_from(Application)
        if stage is not None:
            stmt = stmt.where(Application.status == stage)
        else:
            stmt = stmt.where(Application.status.in_(tuple(ACTIVE_STAGES)))
        return int(self.db.execute(stmt).scalar_one())

    def _stage_counts(self, stage: ApplicationStatus | None) -> dict[str, int]:
        if stage is not None:
            return {stage.value: self._queue_total(stage)}
        rows = self.db.execute(
            select(Application.status, func.count()).group_by(Application.status)
        ).all()
        return {status.value: int(count) for status, count in rows}

    def _last_activity(self, ids: set) -> dict:
        if not ids:
            return {}
        rows = self.db.execute(
            select(AuditLog)
            .where(AuditLog.application_id.in_(ids))
            .order_by(AuditLog.timestamp.desc(), AuditLog.id.desc())
        ).scalars()
        latest: dict = {}
        for entry in rows:
            if entry.application_id in latest:
                continue
            latest[entry.application_id] = WorkspaceActivityRead(
                action=entry.action,
                actor=entry.actor,
                actor_role=entry.actor_role,
                timestamp=entry.timestamp,
                from_status=entry.from_status,
                to_status=entry.to_status,
            )
        return latest

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _actions(
        self,
        role: OfficerRole,
        application: Application,
        verdict: LeaseVerdict,
    ) -> list[WorkspaceActionRead]:
        actions: list[WorkspaceActionRead] = []
        for target in permitted_transitions(role, application):
            blocked: str | None = None
            if (
                application.status is ApplicationStatus.SCRUTINY
                and target in (ApplicationStatus.EVC, ApplicationStatus.SAC)
                and not verdict.compliant
            ):
                blocked = verdict.reason
            actions.append(
                WorkspaceActionRead(
                    to_status=target,
                    label=ACTION_LABEL[target],
                    enabled=blocked is None,
                    blocked_reason=blocked,
                    requires_note=target is ApplicationStatus.REJECTED,
                    is_decision=target
                    in (ApplicationStatus.APPROVED, ApplicationStatus.REJECTED),
                )
            )
        return actions

    # ------------------------------------------------------------------
    # KPIs
    # ------------------------------------------------------------------
    def _kpis(
        self,
        role: OfficerRole,
        dockets: list[WorkspaceDocketRead],
        leases: list[LeaseSnapshotRead],
        attention_total: int,
    ) -> list[WorkspaceKpiRead]:
        if role is OfficerRole.REGIONAL_OFFICER:
            snapshot = analytics.kpis(self.db)
            return [
                WorkspaceKpiRead(
                    key="active",
                    label="Active dockets",
                    value=snapshot.total_active,
                    hint="all desks in the region",
                ),
                WorkspaceKpiRead(
                    key="dwell",
                    label="Past SLA",
                    value=snapshot.dwell_alerts,
                    tone="seal" if snapshot.dwell_alerts else "teal",
                    hint=f"beyond {self.settings.sla_threshold_days} days",
                ),
                WorkspaceKpiRead(
                    key="lease_expiry",
                    label="Lease expiry warnings",
                    value=snapshot.lease_expiry_warnings,
                    tone="turmeric" if snapshot.lease_expiry_warnings else "neutral",
                ),
                WorkspaceKpiRead(
                    key="lease_gaps",
                    label="Lease data gaps",
                    value=snapshot.lease_data_gaps,
                    tone="seal" if snapshot.lease_data_gaps else "neutral",
                ),
                WorkspaceKpiRead(
                    key="approved",
                    label="Approved",
                    value=snapshot.approved,
                    tone="teal",
                ),
                WorkspaceKpiRead(
                    key="blocked",
                    label="Rule 1 blocks",
                    value=snapshot.lease_rule_blocks,
                    tone="turmeric",
                    hint="moves refused by the live-lease rule",
                ),
                WorkspaceKpiRead(
                    key="avg_dwell",
                    label="Average dwell",
                    value=snapshot.avg_dwell_days or 0,
                    unit="days",
                    hint="active dockets",
                ),
            ]

        total = len(dockets)
        breached = sum(1 for docket in dockets if docket.is_sla_breached)
        blocked = sum(1 for lease in leases if not lease.compliant)
        oldest = max((docket.dwell_days for docket in dockets), default=0.0)
        kpis = [
            WorkspaceKpiRead(
                key="queue",
                label="At this desk",
                value=total,
                hint="dockets awaiting your finding",
            ),
            WorkspaceKpiRead(
                key="breached",
                label="Past SLA",
                value=breached,
                tone="seal" if breached else "teal",
                hint=f"beyond {self.settings.sla_threshold_days} days",
            ),
            WorkspaceKpiRead(
                key="oldest",
                label="Oldest dwell",
                value=round(oldest, 1),
                unit="days",
                tone="seal" if oldest > self.settings.sla_threshold_days else "neutral",
            ),
            WorkspaceKpiRead(
                key="blocked",
                label="Lease blocks",
                value=blocked,
                tone="seal" if blocked else "teal",
                hint="cannot move past scrutiny",
            ),
            WorkspaceKpiRead(
                key="attention",
                label="Evidence gaps",
                value=attention_total,
                tone="turmeric" if attention_total else "teal",
                hint="documents not machine-read",
            ),
        ]
        return kpis
