"""Gemini lease extraction: schema parsing, validation and persistence.

No network calls: a stub ``client`` mimics ``google.genai``'s response shape.
"""

from __future__ import annotations

import json
import uuid
from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.models import Document, DocumentType, ExtractionStatus
from app.services.audit import AuditService
from app.services.errors import AIServiceUnavailable, ExtractionError
from app.services.gemini import (
    GeminiLeaseExtractor,
    LeaseExtraction,
    apply_extraction,
    extract_document,
)
from app.services.storage import StorageService

TODAY = date.today()


class _StubModels:
    def __init__(self, text: str):
        self.text = text
        self.calls: list[dict] = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(text=self.text)


class StubClient:
    def __init__(self, text: str):
        self.models = _StubModels(text)


def _payload(**overrides) -> str:
    body = {
        "lease_start_date": "2022-06-01",
        "lease_end_date": "2036-05-31",
        "total_land_area_sqm": 24500.5,
        "survey_numbers": ["112/2", "113"],
    }
    body.update(overrides)
    return json.dumps(body)


def test_extracts_and_validates_complete_deed():
    client = StubClient(_payload())
    extractor = GeminiLeaseExtractor(client=client)

    extraction = extractor.extract(b"%PDF-1.4 lease", "application/pdf")

    assert extraction.is_complete
    assert extraction.lease_start_date == date(2022, 6, 1)
    assert extraction.lease_end_date == date(2036, 5, 31)
    assert extraction.total_land_area_sqm == pytest.approx(24500.5)
    assert extraction.survey_numbers == ["112/2", "113"]
    assert extraction.confidence == 1.0

    call = client.models.calls[0]
    assert call["model"] == "gemini-3.6-flash"
    assert call["config"].response_mime_type == "application/json"
    assert call["config"].temperature == 0.0


def test_accepts_fenced_json_and_survey_string():
    raw = "```json\n" + _payload(survey_numbers="112/2, 113") + "\n```"
    extraction = GeminiLeaseExtractor(client=StubClient(raw)).extract(b"pdf")

    assert extraction.survey_numbers == ["112/2", "113"]
    assert extraction.is_complete


def test_partial_extraction_is_flagged_not_guessed():
    extraction = GeminiLeaseExtractor(
        client=StubClient(_payload(lease_end_date=None, survey_numbers=[]))
    ).extract(b"pdf")

    assert extraction.is_complete is False
    assert extraction.lease_end_date is None
    assert "lease_end_date is missing" in extraction.issues
    assert extraction.confidence < 1.0


def test_contradictory_dates_are_flagged():
    extraction = GeminiLeaseExtractor(
        client=StubClient(_payload(lease_start_date="2030-01-01", lease_end_date="2029-01-01"))
    ).extract(b"pdf")

    assert extraction.is_complete is False
    assert any("later than" in issue for issue in extraction.issues)


def test_malformed_json_raises():
    with pytest.raises(ExtractionError):
        GeminiLeaseExtractor(client=StubClient("not json at all")).extract(b"pdf")


def test_missing_api_key_is_configuration_error():
    extractor = GeminiLeaseExtractor(settings=Settings(gemini_api_key=None))

    with pytest.raises(AIServiceUnavailable) as excinfo:
        extractor.extract(b"pdf")

    assert "GEMINI_API_KEY" in str(excinfo.value)


def test_apply_extraction_projects_fields(make_application, db):
    application = make_application()
    document = Document(
        application_id=application.id,
        doc_type=DocumentType.LEASE_DEED,
        version=1,
        file_name="lease.pdf",
        s3_url="local://x/lease.pdf",
        mime_type="application/pdf",
    )
    db.add(document)
    db.commit()

    extraction = LeaseExtraction(
        lease_start_date=TODAY - timedelta(days=365),
        lease_end_date=TODAY + timedelta(days=3000),
        total_land_area_sqm=12000.0,
        survey_numbers=["45/1"],
        raw={"source": "stub"},
        model="gemini-3.6-flash",
    )
    apply_extraction(document, extraction)

    assert document.extraction_status is ExtractionStatus.EXTRACTED
    assert document.lease_end_date == TODAY + timedelta(days=3000)
    assert document.extraction_model == "gemini-3.6-flash"
    assert document.extraction_confidence == 1.0


def test_extract_document_reads_storage_and_writes_audit(make_application, db):
    application = make_application()
    settings = Settings()
    stored = StorageService(settings).put(
        application_id=application.id,
        document_id=uuid.uuid4(),
        filename="lease.pdf",
        data=b"%PDF-1.4 lease deed",
        mime_type="application/pdf",
    )
    document = Document(
        application_id=application.id,
        doc_type=DocumentType.LEASE_DEED,
        version=1,
        file_name="lease.pdf",
        s3_url=stored.uri,
        mime_type="application/pdf",
    )
    db.add(document)
    db.commit()

    class StubExtractor:
        def extract(self, data: bytes, mime_type: str) -> LeaseExtraction:
            assert data == b"%PDF-1.4 lease deed"
            return LeaseExtraction(
                lease_start_date=TODAY - timedelta(days=500),
                lease_end_date=TODAY + timedelta(days=2000),
                total_land_area_sqm=9000.0,
                survey_numbers=["7/2"],
                raw={"stub": True},
                model="gemini-3.6-flash",
            )

    result = extract_document(db, document, extractor=StubExtractor(), settings=settings)

    assert result.extraction_status is ExtractionStatus.EXTRACTED
    assert result.lease_end_date == TODAY + timedelta(days=2000)
    actions = [entry.action for entry in AuditService(db).timeline(application.id)]
    assert "document.extracted" in actions
    assert AuditService(db).verify(application.id).valid
