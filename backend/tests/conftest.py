"""Shared fixtures: isolated in-memory database + domain factories.

Environment is pinned *before* importing the app so no connection to a real
PostgreSQL/Redis is ever attempted by the test suite.
"""

from __future__ import annotations

import os
import tempfile
import uuid
from collections.abc import Iterator
from datetime import date, timedelta

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("STORAGE_BACKEND", "local")
os.environ.setdefault("LOCAL_STORAGE_DIR", tempfile.mkdtemp(prefix="veriflow-test-uploads-"))
os.environ.setdefault("CELERY_ENABLED", "false")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import create_access_token, hash_password
from app.core.time import utcnow
from app.db.session import get_db
from app.main import app as fastapi_app
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


@pytest.fixture()
def engine():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=Session)


@pytest.fixture()
def db(session_factory) -> Iterator[Session]:
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def _client_with(session_factory, headers: dict[str, str]) -> TestClient:
    def override_get_db() -> Iterator[Session]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    fastapi_app.dependency_overrides[get_db] = override_get_db
    return TestClient(fastapi_app, headers=headers)


@pytest.fixture()
def make_officer(db: Session):
    counter = {"n": 0}

    def _make(
        *,
        role: OfficerRole = OfficerRole.REGIONAL_OFFICER,
        email: str | None = None,
        password: str = "test-password-123",
        region_state: str | None = "Maharashtra",
    ) -> Officer:
        counter["n"] += 1
        officer = Officer(
            email=email or f"officer{counter['n']}@aicte.gov.in",
            full_name=f"Test Officer {counter['n']}",
            designation="Test desk",
            role=role,
            region_state=region_state,
            password_hash=hash_password(password),
            is_active=True,
        )
        db.add(officer)
        db.commit()
        db.refresh(officer)
        return officer

    return _make


@pytest.fixture()
def regional_officer(make_officer) -> Officer:
    return make_officer(role=OfficerRole.REGIONAL_OFFICER)


@pytest.fixture()
def auth_headers(regional_officer: Officer) -> dict[str, str]:
    token = create_access_token(regional_officer).token
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def headers_for():
    """Mint a header set for any officer fixture (stage-desk tests)."""

    def _make(officer: Officer) -> dict[str, str]:
        return {"Authorization": f"Bearer {create_access_token(officer).token}"}

    return _make


@pytest.fixture()
def client(session_factory, auth_headers) -> Iterator[TestClient]:
    test_client = _client_with(session_factory, auth_headers)
    try:
        with test_client:
            yield test_client
    finally:
        fastapi_app.dependency_overrides.clear()


@pytest.fixture()
def anon_client(session_factory) -> Iterator[TestClient]:
    test_client = _client_with(session_factory, {})
    try:
        with test_client:
            yield test_client
    finally:
        fastapi_app.dependency_overrides.clear()


@pytest.fixture()
def institution(db: Session) -> Institution:
    record = Institution(
        aicte_permanent_id="1-12345678",
        name="Test Institute of Technology",
        state="Maharashtra",
        institution_type=InstitutionType.ENGINEERING,
        approved_intake=360,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@pytest.fixture()
def make_application(db: Session, institution: Institution):
    counter = {"n": 0}

    def _make(
        *,
        application_type: ApplicationType = ApplicationType.NEW,
        programme_level: ProgrammeLevel = ProgrammeLevel.UG,
        status: ApplicationStatus = ApplicationStatus.SCRUTINY,
        age_days: int = 0,
        duration: float = 4.0,
        academic_year: str = "2026-27",
        institution_record: Institution | None = None,
    ) -> Application:
        counter["n"] += 1
        owner = institution_record or institution
        application = Application(
            application_number=f"AICTE/TST/{academic_year}/{counter['n']:06d}",
            institution_id=owner.id,
            academic_year=academic_year,
            application_type=application_type,
            programme_level=programme_level,
            max_course_duration_years=duration,
            status=status,
            stage_entry_timestamp=utcnow() - timedelta(days=age_days),
            submitted_at=utcnow() - timedelta(days=age_days + 5),
        )
        db.add(application)
        db.commit()
        db.refresh(application)
        return application

    return _make


@pytest.fixture()
def make_lease(db: Session):
    def _make(
        application: Application,
        *,
        start: date | None = None,
        end: date | None = None,
        version: int = 1,
        extraction_status: ExtractionStatus = ExtractionStatus.EXTRACTED,
    ) -> Document:
        document = Document(
            application_id=application.id,
            doc_type=DocumentType.LEASE_DEED,
            version=version,
            file_name=f"lease-v{version}.pdf",
            s3_url=f"local://{application.id}/lease-v{version}.pdf",
            mime_type="application/pdf",
            lease_start_date=start,
            lease_end_date=end,
            extraction_status=extraction_status,
            extracted_json_data=(
                {
                    "lease_start_date": start.isoformat() if start else None,
                    "lease_end_date": end.isoformat() if end else None,
                    "total_land_area_sqm": 24500.5,
                    "survey_numbers": ["112/2", "113"],
                }
                if start or end
                else None
            ),
            survey_numbers=["112/2", "113"] if start or end else None,
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        return document

    return _make


@pytest.fixture()
def valid_lease_window() -> tuple[date, date]:
    today = date.today()
    return today - timedelta(days=730), today + timedelta(days=3650)


def new_uuid() -> uuid.UUID:  # pragma: no cover - convenience for ad-hoc tests
    return uuid.uuid4()
