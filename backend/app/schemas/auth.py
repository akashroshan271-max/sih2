"""Officer sign-in payloads."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import OfficerRole


class OfficerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: str
    designation: str
    role: OfficerRole
    region_state: str | None = None
    last_login_at: datetime | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    officer: OfficerRead


class DemoAccountRead(OfficerRead):
    """Roster hint for the sign-in screen (development only)."""

    password: str | None = None


class DemoAccountList(BaseModel):
    accounts: list[DemoAccountRead]
    shared_password: str | None = None
    notice: str | None = None
