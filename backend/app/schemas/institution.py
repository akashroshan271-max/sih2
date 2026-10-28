from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import InstitutionType


class InstitutionBase(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    state: str = Field(min_length=2, max_length=64)
    district: str | None = Field(default=None, max_length=64)
    institution_type: InstitutionType
    approved_intake: int = Field(default=0, ge=0, le=100_000)
    is_autonomous: bool = False


class InstitutionCreate(InstitutionBase):
    aicte_permanent_id: str = Field(
        min_length=3,
        max_length=32,
        pattern=r"^[0-9A-Za-z][0-9A-Za-z\-/]*$",
        description="AICTE Permanent ID, e.g. 1-12345678",
    )


class InstitutionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    state: str | None = Field(default=None, min_length=2, max_length=64)
    district: str | None = Field(default=None, max_length=64)
    approved_intake: int | None = Field(default=None, ge=0, le=100_000)
    is_autonomous: bool | None = None


class InstitutionRead(InstitutionBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    aicte_permanent_id: str
    created_at: datetime
    updated_at: datetime


class InstitutionBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    state: str
    institution_type: InstitutionType


class InstitutionListResponse(BaseModel):
    items: list[InstitutionRead]
    total: int
    limit: int
    offset: int
