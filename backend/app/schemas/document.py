from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.models import DocumentType, ExtractionStatus


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    application_id: uuid.UUID
    doc_type: DocumentType
    version: int
    file_name: str
    s3_url: str
    mime_type: str | None = None
    size_bytes: int | None = None
    content_sha256: str | None = None
    uploaded_at: datetime
    uploaded_by: str | None = None

    extraction_status: ExtractionStatus
    extracted_json_data: dict[str, Any] | None = None
    lease_start_date: date | None = None
    lease_end_date: date | None = None
    total_land_area_sqm: float | None = None
    survey_numbers: list[str] | None = None
    extraction_confidence: float | None = None
    extraction_model: str | None = None
    extracted_at: datetime | None = None
    extraction_error: str | None = None
