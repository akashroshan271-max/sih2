"""Officer credential hashing and signed session tokens.

Passwords are stored as bcrypt digests. A successful sign-in mints a short-lived
HS256 JWT carrying the officer id, email and desk (role). The token is the only
thing the browser holds: the API resolves it back to the ``Officer`` row on every
request, so deactivating an officer takes effect immediately.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import Settings, get_settings
from app.core.time import utcnow
from app.models import Officer, OfficerRole
from app.services.errors import Unauthenticated

#: Password shared by the seeded demo officers (development only).
DEMO_PASSWORD = "veriflow@2026"

_BCRYPT_MAX_BYTES = 72
_ALGORITHM = "HS256"


@dataclass(frozen=True)
class IssuedToken:
    token: str
    expires_at: datetime


def hash_password(password: str) -> str:
    encoded = password.encode("utf-8")
    if not encoded or len(encoded) > _BCRYPT_MAX_BYTES:
        raise ValueError("Password must be 1-72 bytes long.")
    return bcrypt.hashpw(encoded, bcrypt.gensalt(rounds=12)).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    if not password or not password_hash:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))
    except ValueError:
        # Malformed digest in the database — fail closed, never 500.
        return False


def create_access_token(
    officer: Officer, *, settings: Settings | None = None, now: datetime | None = None
) -> IssuedToken:
    config = settings or get_settings()
    issued_at = (now or utcnow()).astimezone(timezone.utc)
    expires_at = issued_at + timedelta(minutes=config.auth_token_ttl_minutes)
    payload = {
        "sub": str(officer.id),
        "email": officer.email,
        "name": officer.full_name,
        "role": officer.role.value,
        "iss": config.auth_issuer,
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    token = jwt.encode(payload, config.auth_secret_key, algorithm=_ALGORITHM)
    return IssuedToken(token=token, expires_at=expires_at)


@dataclass(frozen=True)
class TokenClaims:
    officer_id: uuid.UUID
    role: OfficerRole
    email: str
    expires_at: datetime


def decode_access_token(token: str, *, settings: Settings | None = None) -> TokenClaims:
    config = settings or get_settings()
    try:
        payload = jwt.decode(
            token,
            config.auth_secret_key,
            algorithms=[_ALGORITHM],
            issuer=config.auth_issuer,
            options={"require": ["sub", "exp", "iss"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise Unauthenticated("Your session has expired. Please sign in again.") from exc
    except jwt.InvalidTokenError as exc:
        raise Unauthenticated("The session token is not valid.") from exc

    try:
        officer_id = uuid.UUID(str(payload["sub"]))
        role = OfficerRole(str(payload["role"]))
        expires_at = datetime.fromtimestamp(int(payload["exp"]), tz=timezone.utc)
    except (KeyError, ValueError) as exc:
        raise Unauthenticated("The session token is malformed.") from exc

    return TokenClaims(
        officer_id=officer_id,
        role=role,
        email=str(payload.get("email", "")),
        expires_at=expires_at,
    )
