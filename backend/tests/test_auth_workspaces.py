"""Officer sign-in, desk custody and the phase workspaces."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select

from app.core.auth import hash_password
from app.models import ApplicationStatus, ApplicationType, Officer, OfficerRole, ProgrammeLevel

API = "/api/v1"
TODAY = date.today()


def _login(anon_client, officer: Officer, password: str):
    return anon_client.post(
        f"{API}/auth/login",
        json={"email": officer.email, "password": password},
    )


def test_login_issues_a_token_and_records_the_officer(anon_client, db, make_officer):
    officer = make_officer(
        role=OfficerRole.SCRUTINY_OFFICER,
        email="scrutiny.desk@aicte.gov.in",
        password="correct-horse",
    )

    response = _login(anon_client, officer, "correct-horse")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["officer"]["role"] == "scrutiny_officer"
    assert body["officer"]["email"] == "scrutiny.desk@aicte.gov.in"
    assert body["access_token"]

    me = anon_client.get(
        f"{API}/auth/me",
        headers={"Authorization": f"Bearer {body['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["full_name"] == officer.full_name

    db.expire_all()
    persisted = db.execute(select(Officer).where(Officer.id == officer.id)).scalar_one()
    assert persisted.last_login_at is not None


def test_login_failure_is_generic(anon_client, make_officer):
    officer = make_officer(password="right-password")

    wrong = _login(anon_client, officer, "wrong-password")
    assert wrong.status_code == 401
    assert wrong.json()["code"] == "unauthenticated"
    assert "credentials" in wrong.json()["detail"].lower()

    nobody = anon_client.post(
        f"{API}/auth/login",
        json={"email": "nobody@aicte.gov.in", "password": "whatever"},
    )
    assert nobody.status_code == 401
    assert nobody.json()["detail"] == wrong.json()["detail"]


def test_deactivated_officer_is_refused(anon_client, db, make_officer):
    officer = make_officer(password="right-password")
    token = _login(anon_client, officer, "right-password").json()["access_token"]

    officer.is_active = False
    db.commit()

    me = anon_client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 401
    assert me.json()["code"] == "unauthenticated"


def test_malformed_token_is_rejected(anon_client):
    response = anon_client.get(
        f"{API}/applications", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert response.status_code == 401
    assert response.json()["code"] == "unauthenticated"


def test_every_business_route_requires_a_session(anon_client):
    for path in (
        f"{API}/applications",
        f"{API}/institutions",
        f"{API}/dashboard/kpis",
        f"{API}/workspace",
        f"{API}/audit/logs",
    ):
        response = anon_client.get(path)
        assert response.status_code == 401, path


def test_scrutiny_desk_only_sees_and_opens_its_own_stage(
    anon_client, make_officer, headers_for, make_application
):
    scrutiny = make_officer(role=OfficerRole.SCRUTINY_OFFICER)
    at_scrutiny = make_application(application_type=ApplicationType.NEW)
    at_evc = make_application(
        application_type=ApplicationType.EXPANSION,
        programme_level=ProgrammeLevel.PG,
        status=ApplicationStatus.EVC,
    )

    headers = headers_for(scrutiny)
    listing = anon_client.get(f"{API}/applications", headers=headers)
    assert listing.status_code == 200, listing.text
    assert [item["id"] for item in listing.json()["items"]] == [str(at_scrutiny.id)]

    # Even an explicit filter cannot pull another desk's docket.
    escape = anon_client.get(
        f"{API}/applications", params={"status": "evc"}, headers=headers
    )
    assert [item["id"] for item in escape.json()["items"]] == [str(at_scrutiny.id)]

    own = anon_client.get(f"{API}/applications/{at_scrutiny.id}", headers=headers)
    assert own.status_code == 200
    assert own.json()["allowed_transitions"] == ["evc", "rejected"]

    foreign = anon_client.get(f"{API}/applications/{at_evc.id}", headers=headers)
    assert foreign.status_code == 403
    assert foreign.json()["code"] == "forbidden"
    assert foreign.json()["context"]["docket_status"] == "evc"


def test_scrutiny_desk_cannot_act_beyond_scrutiny(
    anon_client, make_officer, headers_for, make_application
):
    scrutiny = make_officer(role=OfficerRole.SCRUTINY_OFFICER)
    downstream = make_application(
        application_type=ApplicationType.EXPANSION,
        programme_level=ProgrammeLevel.PG,
        status=ApplicationStatus.EVC,
    )

    # A move the EVC owns: the scrutiny desk is refused, not merely blocked.
    response = anon_client.post(
        f"{API}/applications/{downstream.id}/transition",
        json={"to_status": "sac"},
        headers=headers_for(scrutiny),
    )
    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"
    assert response.json()["context"]["requested"] == "sac"
    assert response.json()["context"]["permitted"] == []

    # Approval from scrutiny is not a legal transition at all: 409, not 403.
    own = make_application()
    illegal = anon_client.post(
        f"{API}/applications/{own.id}/transition",
        json={"to_status": "approved"},
        headers=headers_for(scrutiny),
    )
    assert illegal.status_code == 409
    assert illegal.json()["code"] == "invalid_transition"


def test_evc_member_forwards_but_cannot_decide(
    anon_client, make_officer, headers_for, make_application, make_lease
):
    evc = make_officer(role=OfficerRole.EVC_MEMBER)
    application = make_application(status=ApplicationStatus.EVC)
    make_lease(
        application,
        start=TODAY - timedelta(days=365),
        end=TODAY + timedelta(days=3650),
    )

    forward = anon_client.post(
        f"{API}/applications/{application.id}/transition",
        json={"to_status": "sac", "remarks": "Site visit satisfactory."},
        headers=headers_for(evc),
    )
    assert forward.status_code == 200, forward.text
    assert forward.json()["to_status"] == "sac"
    assert forward.json()["application"]["allowed_transitions"] == []

    decide = anon_client.post(
        f"{API}/applications/{application.id}/transition",
        json={"to_status": "approved"},
        headers=headers_for(evc),
    )
    assert decide.status_code == 403


def test_sac_member_decides_with_their_own_desk_stamp(
    anon_client, make_officer, headers_for, make_application
):
    sac = make_officer(role=OfficerRole.SAC_MEMBER)
    application = make_application(status=ApplicationStatus.SAC)

    headers = headers_for(sac)
    detail = anon_client.get(f"{API}/applications/{application.id}", headers=headers)
    assert detail.status_code == 200
    assert set(detail.json()["allowed_transitions"]) == {"shc", "approved", "rejected"}

    decision = anon_client.post(
        f"{API}/applications/{application.id}/transition",
        json={"to_status": "approved", "remarks": "Approved for 2026-27."},
        headers=headers,
    )
    assert decision.status_code == 200, decision.text
    assert decision.json()["audit_log"]["actor_role"] == "sac_member"
    assert decision.json()["audit_log"]["actor"] == sac.email


def test_stage_workspace_is_scoped_and_role_specific(
    anon_client, make_officer, headers_for, make_application, make_lease
):
    scrutiny = make_officer(role=OfficerRole.SCRUTINY_OFFICER)
    missing = make_application(application_type=ApplicationType.NEW)
    ready = make_application(
        application_type=ApplicationType.EXPANSION,
        programme_level=ProgrammeLevel.PG,
    )
    make_lease(
        ready,
        start=TODAY - timedelta(days=730),
        end=TODAY + timedelta(days=3650),
    )

    response = anon_client.get(f"{API}/workspace", headers=headers_for(scrutiny))
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["desk"]["stage"] == "scrutiny"
    assert body["desk"]["authority"].startswith("Forward or reject")
    assert body["queue_total"] == 2
    assert {item["id"] for item in body["queue"]} == {str(missing.id), str(ready.id)}
    assert body["stage_counts"] == {"scrutiny": 2}
    assert body["escalations"] == []
    assert {kpi["key"] for kpi in body["kpis"]} >= {"queue", "blocked", "attention"}

    by_id = {item["id"]: item for item in body["queue"]}
    blocked = by_id[str(missing.id)]
    assert blocked["lease"]["compliant"] is False
    assert [action["to_status"] for action in blocked["actions"]] == ["evc", "rejected"]
    assert blocked["actions"][0]["enabled"] is False
    assert blocked["actions"][0]["blocked_reason"]
    assert any(fact["label"] == "Remaining vs required" for fact in blocked["facts"])

    allowed = by_id[str(ready.id)]
    assert allowed["lease"]["compliant"] is True
    assert allowed["actions"][0]["enabled"] is True


def test_oversight_workspace_spans_every_stage(
    anon_client, make_officer, headers_for, make_application
):
    overseer = make_officer(role=OfficerRole.REGIONAL_OFFICER, region_state="Maharashtra")
    make_application(application_type=ApplicationType.NEW)
    make_application(
        application_type=ApplicationType.EXPANSION,
        programme_level=ProgrammeLevel.PG,
        status=ApplicationStatus.EVC,
        age_days=22,
    )

    response = anon_client.get(f"{API}/workspace", headers=headers_for(overseer))
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["desk"]["stage"] is None
    assert body["desk"]["stage_label"] == "All stages"
    assert body["queue_total"] == 2
    assert {item["status"] for item in body["queue"]} == {"scrutiny", "evc"}
    assert body["stage_counts"]["scrutiny"] == 1
    assert body["stage_counts"]["evc"] == 1
    assert len(body["escalations"]) == 1
    assert body["escalations"][0]["level"] == "L1"
    assert {kpi["key"] for kpi in body["kpis"]} >= {
        "active",
        "dwell",
        "approved",
        "blocked",
    }


def test_command_centre_is_oversight_only(
    anon_client, make_officer, headers_for
):
    sac = make_officer(role=OfficerRole.SAC_MEMBER)

    response = anon_client.get(f"{API}/dashboard/kpis", headers=headers_for(sac))
    assert response.status_code == 403
    assert response.json()["context"]["allowed_roles"] == ["regional_officer"]


def test_documents_are_sealed_once_decided(
    anon_client, make_officer, headers_for, make_application
):
    sac = make_officer(role=OfficerRole.SAC_MEMBER)
    decided = make_application(status=ApplicationStatus.APPROVED)

    response = anon_client.post(
        f"{API}/applications/{decided.id}/documents",
        files={"file": ("lease.pdf", b"%PDF-1.4 late", "application/pdf")},
        data={"doc_type": "lease_deed"},
        headers=headers_for(sac),
    )
    assert response.status_code == 403
    assert "sealed" in response.json()["detail"]


def test_demo_roster_lists_every_desk_once(anon_client, db):
    emails = {
        "scrutiny@aicte.gov.in",
        "evc@aicte.gov.in",
        "sac@aicte.gov.in",
        "shc@aicte.gov.in",
        "ro@aicte.gov.in",
    }
    for index, email in enumerate(sorted(emails)):
        db.add(
            Officer(
                email=email,
                full_name=f"Officer {index}",
                designation="Demo",
                role=[
                    OfficerRole.SCRUTINY_OFFICER,
                    OfficerRole.EVC_MEMBER,
                    OfficerRole.SAC_MEMBER,
                    OfficerRole.SHC_MEMBER,
                    OfficerRole.REGIONAL_OFFICER,
                ][index],
                password_hash=hash_password("shared-password"),
            )
        )
    db.commit()

    body = anon_client.get(f"{API}/auth/demo-accounts").json()
    assert body["shared_password"]
    assert {account["role"] for account in body["accounts"]} == {
        "scrutiny_officer",
        "evc_member",
        "sac_member",
        "shc_member",
        "regional_officer",
    }
    assert body["accounts"][0]["role"] == "scrutiny_officer"
