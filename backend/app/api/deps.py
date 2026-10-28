"""Shared request dependencies.

Officer identity comes from a signed JWT presented as ``Authorization: Bearer``.
Every request resolves the token back to an active ``Officer`` row, so the audit
trail always records a real named officer and a deactivated account stops working
immediately. The desk (role) returned here is what the role guards in
:mod:`app.services.permissions` act on.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Annotated, Callable

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.auth import decode_access_token
from app.db.session import get_db
from app.models import Application, Officer, OfficerRole
from app.services.errors import Forbidden, NotFoundError, Unauthenticated

DbSession = Annotated[Session, Depends(get_db)]

#: ``auto_error=False`` lets us return the project's uniform error envelope
#: (``code``/``detail``/``context``) instead of FastAPI's ``{"detail": "..."}``.
bearer_scheme = HTTPBearer(auto_error=False, description="Officer session token")


def get_current_officer(
    db: DbSession,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ] = None,
) -> Officer:
    if credentials is None or not credentials.credentials:
        raise Unauthenticated("Sign in to access the VERIFLOW workspace.")

    claims = decode_access_token(credentials.credentials)
    officer = db.get(Officer, claims.officer_id)
    if officer is None:
        raise Unauthenticated("This officer account no longer exists.")
    if not officer.is_active:
        raise Unauthenticated("This officer account has been deactivated.")
    if officer.role is not claims.role:
        # Desk assignment changed after the token was issued: force a fresh login
        # rather than honour a stale privilege.
        raise Unauthenticated("Your desk assignment changed. Please sign in again.")
    return officer


CurrentOfficer = Annotated[Officer, Depends(get_current_officer)]


@dataclass(frozen=True)
class Actor:
    """Minimal identity written into audit entries."""

    id: str
    role: str
    officer_id: uuid.UUID | None = None
    name: str | None = None

    @property
    def role_enum(self) -> OfficerRole:
        return OfficerRole(self.role)


def get_actor(officer: CurrentOfficer) -> Actor:
    return Actor(
        id=officer.email,
        role=officer.role.value,
        officer_id=officer.id,
        name=officer.full_name,
    )


CurrentActor = Annotated[Actor, Depends(get_actor)]


def require_roles(*allowed: OfficerRole) -> Callable[..., Actor]:
    """Dependency factory: allow only the listed desks."""

    allowed_values = {role.value for role in allowed}

    def _guard(actor: CurrentActor) -> Actor:
        if actor.role not in allowed_values:
            raise Forbidden(
                "Your desk is not authorised for this action.",
                context={"role": actor.role, "allowed_roles": sorted(allowed_values)},
            )
        return actor

    return _guard


def load_application(db: Session, application_id: uuid.UUID) -> Application:
    application = db.get(Application, application_id)
    if application is None:
        raise NotFoundError(f"Application {application_id} was not found.")
    return application


#: Officer roles that may open the regional command centre.
OVERSIGHT_ROLES: tuple[OfficerRole, ...] = (OfficerRole.REGIONAL_OFFICER,)

__all__ = [
    "Actor",
    "CurrentActor",
    "CurrentOfficer",
    "DbSession",
    "OVERSIGHT_ROLES",
    "bearer_scheme",
    "get_actor",
    "get_current_officer",
    "load_application",
    "require_roles",
]
