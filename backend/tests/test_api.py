"""API integration tests (FastAPI TestClient + in-memory database)."""

from __future__ import annotations

import uuid
from datetime import date, timedelta

from app.core.time import utcnow
from app.models import Application, Document, DocumentType, ExtractionStatus
from app.services.gemini import LeaseExtraction

API = "/api/v1"
TODAY = date.today()


def _institution(client, **overrides) -> dict:
    payload = {
        "aicte_permanent_id": "1-87654321",
        "name": "Sunrise Institute of Technology",
        "state": "Karnataka",
        "district": "Bengaluru Urban",
        "institution_type": "engineering",
        "approved_intake": 300,
    }
    payload.update(overrides)
    response = client.post(f"{API}/institutions", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _application(client, institution_id: str, **overrides) -> dict:
    payload = {
        "institution_id": institution_id,
        "academic_year": "2026-27",
        "application_type": "new",
        "programme_level": "ug",
    }
    payload.update(overrides)
    response = client.post(f"{API}/applications", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _age(session_factory, application_id: str, days: int) -> None:
    with session_factory() as session:
        application = session.get(Application, uuid.UUID(application_id))
        assert application is not None
        application.stage_entry_timestamp = utcnow() - timedelta(days=days)
        session.commit()


def _attach_lease(session_factory, application_id: str, *, days_left: int = 3000) -> uuid.UUID:
    with session_factory() as session:
        document = Document(
            application_id=uuid.UUID(application_id),
            doc_type=DocumentType.LEASE_DEED,
            version=1,
            file_name="lease.pdf",
            s3_url="local://seed/lease.pdf",
            mime_type="application/pdf",
            lease_start_date=TODAY - timedelta(days=400),
            lease_end_date=TODAY + timedelta(days=days_left),
            extraction_status=ExtractionStatus.EXTRACTED,
            survey_numbers=["112/2"],
        )
        session.add(document)
        session.commit()
        session.refresh(document)
        document_id = document.id
    return document_id


# =============================================================================
# Intake
# =============================================================================


def test_institution_and_application_intake(client):
    institution = _institution(client)

    application = _application(client, institution["id"])

    assert application["application_number"].startswith("AICTE/KA/2026-27/")
    assert application["status"] == "scrutiny"
    assert application["max_course_duration_years"] == 4.0
    assert application["lease_verdict"]["code"] == "lease_deed_missing"
    assert application["allowed_transitions"] == ["evc", "rejected"]
    assert application["institution"]["name"] == "Sunrise Institute of Technology"
    assert application["documents"] == []
    assert [entry["action"] for entry in application["audit_trail"]] == ["application.created"]
    assert len(application["audit_trail"][0]["sha256_hash"]) == 64


def test_application_intake_validation(client):
    institution = _institution(client)
    _application(client, institution["id"])

    duplicate = client.post(
        f"{API}/applications",
        json={
            "institution_id": institution["id"],
            "academic_year": "2026-27",
            "application_type": "new",
            "programme_level": "ug",
        },
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "conflict"

    bad_year = client.post(
        f"{API}/applications",
        json={
            "institution_id": institution["id"],
            "academic_year": "2026",
            "application_type": "new",
            "programme_level": "ug",
        },
    )
    assert bad_year.status_code == 422


# =============================================================================
# Rule 1 over HTTP
# =============================================================================


def test_lease_rule_blocks_transition_with_422(client):
    institution = _institution(client)
    application = _application(client, institution["id"])

    response = client.post(
        f"{API}/applications/{application['id']}/transition",
        json={"to_status": "evc", "remarks": "Ready for expert visit"},
    )

    assert response.status_code == 422, response.text
    body = response.json()
    assert body["code"] == "lease_rule_blocked"
    assert body["context"]["lease_verdict"]["code"] == "lease_deed_missing"

    detail = client.get(f"{API}/applications/{application['id']}").json()
    assert detail["status"] == "scrutiny"

    trail = client.get(f"{API}/applications/{application['id']}/audit").json()
    assert trail[-1]["action"] == "lease_rule.blocked"


def test_transition_succeeds_with_a_live_lease(client, session_factory):
    institution = _institution(client)
    application = _application(client, institution["id"])
    _attach_lease(session_factory, application["id"], days_left=3650)

    response = client.post(
        f"{API}/applications/{application['id']}/transition",
        json={"to_status": "evc", "remarks": "Lease verified"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["to_status"] == "evc"
    assert body["lease_verdict"]["code"] == "lease_valid"
    assert body["application"]["status"] == "evc"
    assert body["application"]["lease_verdict"]["compliant"] is True

    verify = client.get(f"{API}/audit/applications/{application['id']}/verify").json()
    assert verify["verification"]["valid"] is True
    assert verify["verification"]["checked"] == 2  # application.created + stage.transition


def test_invalid_transition_returns_409(client):
    institution = _institution(client)
    application = _application(client, institution["id"])

    response = client.post(
        f"{API}/applications/{application['id']}/transition",
        json={"to_status": "approved"},
    )

    assert response.status_code == 409
    assert response.json()["code"] == "invalid_transition"


# =============================================================================
# Documents & extraction
# =============================================================================


def test_document_upload_versions_and_validation(client):
    institution = _institution(client)
    application = _application(client, institution["id"])
    url = f"{API}/applications/{application['id']}/documents"

    first = client.post(
        url,
        files={"file": ("lease.pdf", b"%PDF-1.4 first", "application/pdf")},
        data={"doc_type": "lease_deed"},
    )
    assert first.status_code == 201, first.text
    assert first.json()["version"] == 1
    assert first.json()["extraction_status"] == "pending"
    assert len(first.json()["content_sha256"]) == 64

    second = client.post(
        url,
        files={"file": ("lease-v2.pdf", b"%PDF-1.4 second", "application/pdf")},
        data={"doc_type": "lease_deed"},
    )
    assert second.status_code == 201
    assert second.json()["version"] == 2

    listed = client.get(url).json()
    assert [document["version"] for document in listed] == [1, 2]

    unsupported = client.post(
        url,
        files={"file": ("notes.txt", b"hello", "text/plain")},
        data={"doc_type": "lease_deed"},
    )
    assert unsupported.status_code == 422
    assert unsupported.json()["code"] == "validation_failed"


def test_extraction_endpoint_marks_document_and_returns_verdict(
    client, monkeypatch
):
    institution = _institution(client)
    application = _application(client, institution["id"])
    upload = client.post(
        f"{API}/applications/{application['id']}/documents",
        files={"file": ("lease.pdf", b"%PDF-1.4 lease", "application/pdf")},
        data={"doc_type": "lease_deed"},
    )
    document_id = upload.json()["id"]

    def fake_extract(self, data: bytes, mime_type: str = "application/pdf") -> LeaseExtraction:
        assert data.startswith(b"%PDF")
        return LeaseExtraction(
            lease_start_date=TODAY - timedelta(days=500),
            lease_end_date=TODAY + timedelta(days=2000),
            total_land_area_sqm=18500.0,
            survey_numbers=["77/1"],
            raw={"stub": True},
            model="gemini-3.6-flash",
        )

    monkeypatch.setattr(
        "app.services.gemini.GeminiLeaseExtractor.extract",
        fake_extract,
    )

    response = client.post(f"{API}/documents/{document_id}/extract")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["document"]["extraction_status"] == "extracted"
    assert body["document"]["lease_end_date"] == (TODAY + timedelta(days=2000)).isoformat()
    assert body["document"]["survey_numbers"] == ["77/1"]
    assert body["lease_verdict"]["code"] == "lease_valid"


# =============================================================================
# Dashboard
# =============================================================================


def test_dashboard_endpoints(client, session_factory):
    institution = _institution(client)
    fresh = _application(client, institution["id"])
    stale = _application(
        client,
        institution["id"],
        application_type="renewal",
        programme_level="pg",
    )
    _age(session_factory, stale["id"], 22)
    _attach_lease(session_factory, fresh["id"], days_left=3650)

    kpis = client.get(f"{API}/dashboard/kpis")
    assert kpis.status_code == 200
    body = kpis.json()
    assert body["total_active"] == 2
    assert body["dwell_alerts"] == 1
    assert body["lease_data_gaps"] == 1  # renewal docket has no lease deed
    assert body["lease_expiry_warnings"] == 0
    assert {stage["status"] for stage in body["stages"]} == {"scrutiny", "evc", "sac", "shc"}

    pipeline = client.get(f"{API}/dashboard/pipeline").json()
    scrutiny = next(column for column in pipeline["columns"] if column["status"] == "scrutiny")
    assert scrutiny["count"] == 2
    assert len(scrutiny["applications"]) == 2
    # Oldest docket first — the officer's queue is dwell-time ordered.
    assert scrutiny["applications"][0]["id"] == stale["id"]

    heatmap = client.get(f"{API}/dashboard/sla-heatmap").json()
    assert heatmap["threshold_days"] == 15
    assert any(cell["state"] == "Karnataka" and cell["breached"] == 1 for cell in heatmap["cells"])

    funnel = client.get(f"{API}/dashboard/funnel").json()
    scrutiny_step = next(step for step in funnel["steps"] if step["status"] == "scrutiny")
    assert scrutiny_step["count"] == 2
    assert funnel["total"] == 2

    alerts = client.get(f"{API}/dashboard/sla-alerts").json()
    assert alerts["total"] == 1
    assert alerts["levels"] == {"L1": 1}
    assert alerts["items"][0]["escalate_to"] == "Concerned Dealing Officer"

    warnings = client.get(f"{API}/dashboard/lease-warnings").json()
    assert warnings["total"] == 1
    assert warnings["items"][0]["code"] == "lease_deed_missing"

    scan = client.post(f"{API}/dashboard/sla/scan")
    assert scan.status_code == 200
    assert scan.json()["escalated"] == 1
    assert scan.json()["levels"] == {"L1": 1}

    repeat = client.post(f"{API}/dashboard/sla/scan").json()
    assert repeat["escalated"] == 0


def test_health_and_openapi(client):
    health = client.get("/health").json()
    assert health["status"] == "ok"
    assert health["database"] == "up"

    schema = client.get(f"{API}/openapi.json").json()
    assert f"{API}/applications" in schema["paths"]
