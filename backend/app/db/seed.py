"""Seed a demo dataset for the command centre.

    python -m app.db.seed --reset      # drop + recreate schema, then seed
    python -m app.db.seed              # seed only if the registry is empty

The dataset is deliberately shaped to exercise every dashboard state: dockets
at each stage, SLA breaches at L1/L2/L3, a short lease, a missing lease and an
untouched extraction.
"""

from __future__ import annotations

import argparse
import re
from datetime import timedelta

from sqlalchemy import func, select

from app.core.auth import DEMO_PASSWORD, hash_password
from app.core.config import get_settings
from app.core.time import utcnow
from app.db.session import SessionLocal, engine
from app.models import (
    Application,
    ApplicationStatus,
    ApplicationType,
    Base,
    Document,
    DocumentType,
    ExtractionStatus,
    Institution,
    InstitutionType,
    Officer,
    OfficerRole,
    ProgrammeLevel,
)
from app.services.audit import AuditService

INSTITUTIONS: list[tuple[str, str, str, InstitutionType, int]] = [
    ("1-11000001", "Sinhgad College of Engineering", "Maharashtra", InstitutionType.ENGINEERING, 480),
    ("1-11000002", "BMS Institute of Technology", "Karnataka", InstitutionType.ENGINEERING, 420),
    ("1-11000003", "PSG College of Technology", "Tamil Nadu", InstitutionType.ENGINEERING, 540),
    ("1-11000004", "Nirma Institute of Pharmacy", "Gujarat", InstitutionType.PHARMACY, 120),
    ("1-11000005", "Amity Business School", "Uttar Pradesh", InstitutionType.MANAGEMENT, 240),
    ("1-11000006", "Heritage Institute of Technology", "West Bengal", InstitutionType.ENGINEERING, 360),
    ("1-11000007", "VNR Vignana Jyothi Institute", "Telangana", InstitutionType.ENGINEERING, 300),
    ("1-11000008", "Poornima Polytechnic", "Rajasthan", InstitutionType.POLYTECHNIC, 180),
]

#: (application_type, programme_level, duration, final status, dwell days, lease profile)
TEMPLATES = [
    (ApplicationType.NEW, ProgrammeLevel.UG, 4.0, ApplicationStatus.SCRUTINY, 20, "missing"),
    (ApplicationType.EXPANSION, ProgrammeLevel.UG, 4.0, ApplicationStatus.EVC, 35, "short"),
    (ApplicationType.RENEWAL, ProgrammeLevel.PG, 2.0, ApplicationStatus.SAC, 8, "valid"),
    (ApplicationType.NEW, ProgrammeLevel.DIPLOMA, 3.0, ApplicationStatus.APPROVED, 60, "valid"),
    (ApplicationType.NEW, ProgrammeLevel.UG, 4.0, ApplicationStatus.SCRUTINY, 3, "valid"),
    (ApplicationType.EXPANSION, ProgrammeLevel.PG, 2.0, ApplicationStatus.EVC, 12, "valid"),
    (ApplicationType.NEW, ProgrammeLevel.PG, 2.0, ApplicationStatus.SAC, 18, "short"),
    (ApplicationType.CLOSURE, ProgrammeLevel.UG, 3.0, ApplicationStatus.APPROVED, 40, "valid"),
    (ApplicationType.NEW, ProgrammeLevel.DIPLOMA, 3.0, ApplicationStatus.SCRUTINY, 0, "valid"),
    (ApplicationType.EXPANSION, ProgrammeLevel.UG, 4.0, ApplicationStatus.SAC, 24, "valid"),
]

FLOW: dict[ApplicationStatus, list[tuple[ApplicationStatus, ApplicationStatus]]] = {
    ApplicationStatus.SCRUTINY: [],
    ApplicationStatus.EVC: [(ApplicationStatus.SCRUTINY, ApplicationStatus.EVC)],
    ApplicationStatus.SAC: [
        (ApplicationStatus.SCRUTINY, ApplicationStatus.EVC),
        (ApplicationStatus.EVC, ApplicationStatus.SAC),
    ],
    ApplicationStatus.APPROVED: [
        (ApplicationStatus.SCRUTINY, ApplicationStatus.EVC),
        (ApplicationStatus.EVC, ApplicationStatus.SAC),
        (ApplicationStatus.SAC, ApplicationStatus.APPROVED),
    ],
}

YEAR = "2026-27"

#: One demo officer per statutory desk. All share ``DEMO_PASSWORD``.
OFFICERS: list[tuple[str, str, str, OfficerRole, str | None]] = [
    (
        "scrutiny.officer@aicte.gov.in",
        "Meera Iyer",
        "Dealing Officer, Scrutiny Cell",
        OfficerRole.SCRUTINY_OFFICER,
        None,
    ),
    (
        "evc.member@aicte.gov.in",
        "Dr. Arvind Rao",
        "Member, Expert Visit Committee",
        OfficerRole.EVC_MEMBER,
        None,
    ),
    (
        "sac.member@aicte.gov.in",
        "Prof. Nandita Sen",
        "Member, Standing Approval Committee",
        OfficerRole.SAC_MEMBER,
        None,
    ),
    (
        "shc.member@aicte.gov.in",
        "K. Menon",
        "Chairperson, Standing Hearing Committee",
        OfficerRole.SHC_MEMBER,
        None,
    ),
    (
        "ro.mumbai@aicte.gov.in",
        "Rakesh Deshmukh",
        "Regional Officer, Western Region",
        OfficerRole.REGIONAL_OFFICER,
        "Maharashtra",
    ),
]

#: Actor metadata for the seeded workflow history, by the stage being left.
SEEDED_ACTORS: dict[ApplicationStatus, tuple[str, str]] = {
    ApplicationStatus.SCRUTINY: ("scrutiny.officer@aicte.gov.in", "scrutiny_officer"),
    ApplicationStatus.EVC: ("evc.member@aicte.gov.in", "evc_member"),
    ApplicationStatus.SAC: ("sac.member@aicte.gov.in", "sac_member"),
    ApplicationStatus.SHC: ("shc.member@aicte.gov.in", "shc_member"),
}


def _seed_officers(db) -> int:
    """Create any missing demo officers; safe to re-run."""
    existing = set(db.execute(select(Officer.email)).scalars())
    missing = [record for record in OFFICERS if record[0] not in existing]
    if not missing:
        return 0

    digest = hash_password(DEMO_PASSWORD)
    for email, full_name, designation, role, region_state in missing:
        db.add(
            Officer(
                email=email,
                full_name=full_name,
                designation=designation,
                role=role,
                region_state=region_state,
                password_hash=digest,
                is_active=True,
            )
        )
    db.commit()
    return len(missing)


def _state_code(state: str) -> str:
    return re.sub(r"[^A-Z]", "", state.upper())[:2] or "IN"


def _lease_document(application: Application, profile: str, now) -> Document | None:
    if profile == "missing":
        return None

    if profile == "short":
        start, end = now.date() - timedelta(days=1825), now.date() + timedelta(days=700)
        extraction = ExtractionStatus.EXTRACTED
    elif profile == "valid":
        start, end = now.date() - timedelta(days=1460), now.date() + timedelta(days=3650)
        extraction = ExtractionStatus.EXTRACTED
    else:  # unextracted
        start, end = None, None
        extraction = ExtractionStatus.PENDING

    return Document(
        application_id=application.id,
        doc_type=DocumentType.LEASE_DEED,
        version=1,
        file_name="registered-lease-deed.pdf",
        s3_url=f"local://{application.id}/registered-lease-deed.pdf",
        mime_type="application/pdf",
        size_bytes=412_000,
        extraction_status=extraction,
        lease_start_date=start,
        lease_end_date=end,
        total_land_area_sqm=24_500.5 if start else None,
        survey_numbers=["112/2", "113"] if start else None,
        extracted_json_data=(
            {
                "lease_start_date": start.isoformat(),
                "lease_end_date": end.isoformat(),
                "total_land_area_sqm": 24_500.5,
                "survey_numbers": ["112/2", "113"],
            }
            if start
            else None
        ),
        extraction_model="gemini-3.6-flash" if start else None,
        extraction_confidence=0.98 if start else None,
    )


def seed(reset: bool = False) -> dict[str, int]:
    settings = get_settings()
    if settings.environment == "production":
        raise SystemExit("Refusing to seed a production environment.")

    if reset:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    now = utcnow()
    counts = {
        "officers": 0,
        "institutions": 0,
        "applications": 0,
        "documents": 0,
        "audit_entries": 0,
    }

    with SessionLocal() as db:
        # Officers are seeded independently so an existing demo dataset can pick
        # up new desk accounts without a destructive --reset.
        counts["officers"] = _seed_officers(db)
        if not reset and db.execute(select(func.count()).select_from(Institution)).scalar_one():
            return counts

        audit = AuditService(db)
        sequence = 0
        scrutiny_seen = 0

        for inst_index, (permanent_id, name, state, kind, intake) in enumerate(INSTITUTIONS, start=1):
            institution = Institution(
                aicte_permanent_id=permanent_id,
                name=name,
                state=state,
                institution_type=kind,
                approved_intake=intake,
                is_autonomous=kind is InstitutionType.ENGINEERING,
            )
            db.add(institution)
            db.flush()
            counts["institutions"] += 1

            for sequence_offset, (_t0, _t1, duration, final_status, age_days, profile) in enumerate(TEMPLATES, start=1):
                sequence += 1
                # Each per-institution slot gets a distinct (year, type, level) so
                # the five-institution seed produces 5 x 10 = 50 dockets without
                # hitting the uniqueness constraint on (institution, year, type, level).
                year_slot = (sequence_offset - 1) % 4
                years = ["2026-27", "2025-26", "2027-28", "2024-25"]
                cycle_index = (sequence_offset // 4 + inst_index) % 3
                levels = [ProgrammeLevel.UG, ProgrammeLevel.PG, ProgrammeLevel.DIPLOMA]
                app_type = [ApplicationType.NEW, ApplicationType.EXPANSION, ApplicationType.RENEWAL][
                    (year_slot + cycle_index) % 3
                ]
                level = levels[(year_slot + cycle_index) % 3]
                academic_year = years[year_slot]
                # Alternate the scrutiny queue between a registered live lease
                # and no deed at all, so the same desk can demonstrate a
                # forward move *and* the Rule 1 missing-lease block.
                if final_status is ApplicationStatus.SCRUTINY:
                    scrutiny_seen += 1
                    if scrutiny_seen % 2 == 1:
                        profile = "valid"
                hops = FLOW[final_status]
                submitted = now - timedelta(days=age_days + 20 * (len(hops) + 1))
                stage_entry = now - timedelta(days=age_days)

                application = Application(
                    application_number=f"AICTE/{_state_code(state)}/{academic_year}/{sequence:06d}",
                    institution_id=institution.id,
                    academic_year=academic_year,
                    application_type=app_type,
                    programme_level=level,
                    max_course_duration_years=duration,
                    status=final_status,
                    stage_entry_timestamp=stage_entry,
                    submitted_at=submitted,
                    proposed_intake=intake + 60,
                    decided_at=stage_entry if final_status is ApplicationStatus.APPROVED else None,
                    decision_remarks=(
                        "Approved by SAC for the 2026-27 session."
                        if final_status is ApplicationStatus.APPROVED
                        else None
                    ),
                )
                db.add(application)
                db.commit()
                db.refresh(application)
                counts["applications"] += 1

                audit.record(
                    application=application,
                    action="application.created",
                    actor="institution.portal",
                    actor_role="applicant",
                    to_status=ApplicationStatus.SCRUTINY,
                    payload={"application_type": app_type.value, "academic_year": YEAR},
                    occurred_at=submitted,
                )
                counts["audit_entries"] += 1

                for index, (from_status, to_status) in enumerate(hops):
                    occurred = submitted + (stage_entry - submitted) * (index + 1) / len(hops)
                    actor_email, actor_role = SEEDED_ACTORS[from_status]
                    audit.record(
                        application=application,
                        action="stage.transition",
                        actor=actor_email,
                        actor_role=actor_role,
                        from_status=from_status,
                        to_status=to_status,
                        payload={"remarks": "Seeded workflow step."},
                        occurred_at=occurred,
                    )
                    counts["audit_entries"] += 1

                document = _lease_document(application, profile, now)
                if document is not None:
                    db.add(document)
                    counts["documents"] += 1

                db.commit()

    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed VERIFLOW-AICTE demo data")
    parser.add_argument("--reset", action="store_true", help="drop and recreate all tables")
    args = parser.parse_args()
    counts = seed(reset=args.reset)
    if not any(counts.values()):
        print("Database already seeded; use --reset to rebuild.")
        return
    summary = " · ".join(
        f"{value} {name.replace('_', ' ')}" for name, value in counts.items() if value
    )
    print(f"Seeded: {summary}")


if __name__ == "__main__":
    main()
