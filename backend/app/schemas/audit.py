from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.models import ApplicationStatus


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    application_id: uuid.UUID
    action: str
    actor: str
    actor_role: str | None = None
    from_status: ApplicationStatus | None = None
    to_status: ApplicationStatus | None = None
    payload: dict[str, Any] | None = None
    timestamp: datetime
    sha256_hash: str
    previous_hash: str | None = None


class ChainVerificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    valid: bool
    checked: int
    broken_at: int | None = None
    entry_id: str | None = None
    expected_hash: str | None = None
    stored_hash: str | None = None
    reason: str | None = None


class AuditListResponse(BaseModel):
    items: list[AuditLogRead]
    total: int


class ChainVerificationResponse(BaseModel):
    application_id: uuid.UUID
    application_number: str
    verification: ChainVerificationRead
