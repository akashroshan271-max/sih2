"""Officer sign-in.

Credentials are checked against the bcrypt digest on the ``Officer`` row and a
signed JWT is issued. The token carries only identity and desk; every request
re-resolves the officer, so a desk change or deactivation invalidates it.
"""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.deps import CurrentOfficer, DbSession
from app.core.auth import DEMO_PASSWORD, create_access_token, verify_password
from app.core.config import get_settings
from app.core.time import utcnow
from app.models import Officer, OfficerRole
from app.schemas.auth import (
    DemoAccountList,
    DemoAccountRead,
    LoginRequest,
    LoginResponse,
    OfficerRead,
)
from app.services.errors import Forbidden, Unauthenticated

router = APIRouter(prefix="/auth", tags=["auth"])

ROLE_ORDER: dict[OfficerRole, int] = {
    OfficerRole.SCRUTINY_OFFICER: 0,
    OfficerRole.EVC_MEMBER: 1,
    OfficerRole.SAC_MEMBER: 2,
    OfficerRole.SHC_MEMBER: 3,
    OfficerRole.REGIONAL_OFFICER: 4,
}


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: DbSession) -> LoginResponse:
    officer = db.execute(
        select(Officer).where(func.lower(Officer.email) == payload.email.lower())
    ).scalar_one_or_none()

    # One generic failure for unknown email, inactive account and bad password:
    # the response must not reveal which of those it was.
    if (
        officer is None
        or not officer.is_active
        or not verify_password(payload.password, officer.password_hash)
    ):
        raise Unauthenticated("Those credentials are not recognised.")

    officer.last_login_at = utcnow()
    db.commit()
    db.refresh(officer)

    issued = create_access_token(officer)
    return LoginResponse(
        access_token=issued.token,
        expires_at=issued.expires_at,
        officer=OfficerRead.model_validate(officer),
    )


@router.get("/me", response_model=OfficerRead)
def me(officer: CurrentOfficer) -> OfficerRead:
    return OfficerRead.model_validate(officer)


@router.post("/logout")
def logout(officer: CurrentOfficer) -> dict[str, bool]:
    """Stateless sign-out; the client discards the token."""
    return {"signed_out": True}


@router.get("/demo-accounts", response_model=DemoAccountList)
def demo_accounts(db: DbSession) -> DemoAccountList:
    """Roster shown on the sign-in screen in non-production environments."""
    settings = get_settings()
    if settings.environment == "production":
        raise Forbidden("The demo roster is not available in production.")

    officers = list(db.execute(select(Officer).where(Officer.is_active.is_(True))).scalars())
    officers.sort(key=lambda officer: ROLE_ORDER.get(officer.role, 99))
    return DemoAccountList(
        accounts=[
            DemoAccountRead(
                **OfficerRead.model_validate(officer).model_dump(),
                password=DEMO_PASSWORD,
            )
            for officer in officers
        ],
        shared_password=DEMO_PASSWORD,
        notice=(
            "Demo officers for the hackathon build. Each desk sees only the "
            "dockets at its own stage."
        ),
    )
