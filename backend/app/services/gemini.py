"""AI document intelligence — Land Lease Deed extraction (``google-genai``).

The extractor sends the deed (PDF or scanned image) to ``gemini-3.6-flash``
with a strict response schema and returns a validated:class:`LeaseExtraction`.
Nothing is written to the database until every field has been type-checked, so
a hallucinated or truncated response can never leak into a compliance decision:

* all four APH fields are requested;
* the model is told to return ``null`` rather than guess;
* a partial or contradictory extraction lands in ``NEEDS_REVIEW`` instead of
  silently satisfying Rule 1.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.time import utcnow
from app.models import (
    Application,
    Document,
    DocumentType,
    ExtractionStatus,
)
from app.services.audit import AuditService
from app.services.errors import (
    AIServiceUnavailable,
    DomainError,
    ExtractionError,
)
from app.services.storage import StorageService

LEASE_PROMPT = """You are a land-records analyst verifying documents for the AICTE \
statutory approval process (Approval Process Handbook 2024-27).

Read the attached Land Lease Deed (it may be a scan, a photograph, or typed text, \
and may be in English or a regional language) and extract ONLY facts that are \
explicitly stated in the document.

Return a JSON object with exactly these keys:
  lease_start_date     "YYYY-MM-DD"  commencement / effective date of the lease
  lease_end_date       "YYYY-MM-DD"  expiry date, including any registered extension
  total_land_area_sqm  number        total demised land area in square metres
  survey_numbers       array[string] survey / gat / khasra / plot numbers

Rules:
1. Convert area units to square metres: 1 acre = 4046.8564224, 1 hectare = 10000,
   1 square foot = 0.09290304, 1 square yard = 0.83612736.
2. Use the registered lease deed's dates, not the stamp-paper purchase date.
3. List every survey number individually as a string; do not merge ranges.
4. If a value is illegible, missing, or ambiguous, return null (or [] for
   survey_numbers). Never estimate, infer, or fabricate a value.
5. Return only the JSON object, with no markdown fences or commentary."""

LEASE_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "lease_start_date": {
            "type": "STRING",
            "description": "Lease commencement date as YYYY-MM-DD, or null.",
            "nullable": True,
        },
        "lease_end_date": {
            "type": "STRING",
            "description": "Lease expiry date as YYYY-MM-DD, or null.",
            "nullable": True,
        },
        "total_land_area_sqm": {
            "type": "NUMBER",
            "description": "Total demised land area in square metres, or null.",
            "nullable": True,
        },
        "survey_numbers": {
            "type": "ARRAY",
            "description": "Survey / gat / khasra / plot numbers as strings.",
            "items": {"type": "STRING"},
        },
    },
    "required": [
        "lease_start_date",
        "lease_end_date",
        "total_land_area_sqm",
        "survey_numbers",
    ],
}

DEFAULT_MIME_TYPE = "application/pdf"
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


@dataclass(frozen=True)
class LeaseExtraction:
    lease_start_date: date | None
    lease_end_date: date | None
    total_land_area_sqm: float | None
    survey_numbers: list[str]
    raw: dict[str, Any]
    model: str
    issues: tuple[str, ...] = ()

    @property
    def is_complete(self) -> bool:
        return not self.issues

    @property
    def confidence(self) -> float:
        """Fraction of statutory fields present, penalised for contradictions."""
        present = sum(
            1
            for value in (
                self.lease_start_date,
                self.lease_end_date,
                self.total_land_area_sqm,
                self.survey_numbers or None,
            )
            if value is not None
        )
        score = present / 4
        if self.issues:
            score = max(0.0, score - 0.1)
        return round(score, 3)

    def as_payload(self) -> dict[str, Any]:
        return {
            "lease_start_date": self.lease_start_date.isoformat() if self.lease_start_date else None,
            "lease_end_date": self.lease_end_date.isoformat() if self.lease_end_date else None,
            "total_land_area_sqm": self.total_land_area_sqm,
            "survey_numbers": self.survey_numbers,
            "model": self.model,
            "confidence": self.confidence,
            "issues": list(self.issues),
        }


class LeaseExtractor(Protocol):
    def extract(self, data: bytes, mime_type: str) -> LeaseExtraction: ...


class GeminiLeaseExtractor:
    """Thin, injectable wrapper around ``google-genai``."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        client: Any | None = None,
        model: str | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.model = model or self.settings.gemini_model
        self._client = client

    # ------------------------------------------------------------------
    def extract(self, data: bytes, mime_type: str = DEFAULT_MIME_TYPE) -> LeaseExtraction:
        if not data:
            raise ExtractionError("The uploaded document is empty.")

        client = self._ensure_client()
        try:
            from google.genai import types
        except ImportError as exc:  # pragma: no cover
            raise AIServiceUnavailable(
                "google-genai is not installed; run pip install -r requirements.txt."
            ) from exc

        try:
            response = client.models.generate_content(
                model=self.model,
                contents=[
                    types.Part.from_bytes(data=data, mime_type=mime_type),
                    LEASE_PROMPT,
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=LEASE_RESPONSE_SCHEMA,
                    temperature=0.0,
                ),
            )
        except Exception as exc:
            raise ExtractionError(f"Gemini request failed: {exc}") from exc

        text = getattr(response, "text", None)
        if not text:
            raise ExtractionError(
                "Gemini returned no text (the response may have been blocked by safety filters)."
            )

        payload = _loads_json(text)
        if not isinstance(payload, dict):
            raise ExtractionError("Gemini did not return a JSON object.")

        return self._validate(payload)

    # ------------------------------------------------------------------
    def _ensure_client(self) -> Any:
        if self._client is not None:
            return self._client
        api_key = self.settings.gemini_api_key
        if not api_key:
            raise AIServiceUnavailable(
                "GEMINI_API_KEY is not configured. Set it in the backend .env to run "
                "document extraction."
            )

        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:  # pragma: no cover
            raise AIServiceUnavailable(
                "google-genai is not installed; run pip install -r requirements.txt."
            ) from exc

        self._client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                timeout=int(self.settings.gemini_timeout_seconds * 1000)
            ),
        )
        return self._client

    def _validate(self, payload: dict[str, Any]) -> LeaseExtraction:
        issues: list[str] = []

        lease_start = _parse_date(payload.get("lease_start_date"), "lease_start_date", issues)
        lease_end = _parse_date(payload.get("lease_end_date"), "lease_end_date", issues)
        area = _parse_area(payload.get("total_land_area_sqm"), issues)
        surveys = _parse_surveys(payload.get("survey_numbers"), issues)

        if lease_start and lease_end and lease_end <= lease_start:
            issues.append("lease_end_date must be later than lease_start_date")
        if area is not None and area <= 0:
            issues.append("total_land_area_sqm must be positive")

        return LeaseExtraction(
            lease_start_date=lease_start,
            lease_end_date=lease_end,
            total_land_area_sqm=area,
            survey_numbers=surveys,
            raw=payload,
            model=self.model,
            issues=tuple(issues),
        )


# =============================================================================
# Parsing / coercion helpers
# =============================================================================


def _loads_json(text: str) -> Any:
    cleaned = _FENCE.sub("", text.strip()).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Last resort: pull the outermost JSON object out of stray prose.
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError:
                pass
    raise ExtractionError("Gemini returned malformed JSON.")


def _parse_date(value: Any, label: str, issues: list[str]) -> date | None:
    if value in (None, "", "null"):
        issues.append(f"{label} is missing")
        return None
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except ValueError:
        issues.append(f"{label} is not a valid YYYY-MM-DD date")
        return None


def _parse_area(value: Any, issues: list[str]) -> float | None:
    if value in (None, "", "null"):
        issues.append("total_land_area_sqm is missing")
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        issues.append("total_land_area_sqm is not numeric")
        return None


def _parse_surveys(value: Any, issues: list[str]) -> list[str]:
    if value in (None, "", "null"):
        issues.append("survey_numbers is missing")
        return []
    if isinstance(value, str):
        # Only commas/semicolons separate numbers: "112/2" is one survey number,
        # so splitting on "/" would corrupt it.
        parts = [part.strip() for part in re.split(r"[,;]", value) if part.strip()]
        if parts:
            return parts
    if isinstance(value, (list, tuple)):
        surveys = [str(item).strip() for item in value if str(item).strip()]
        if surveys:
            return surveys
    issues.append("survey_numbers is empty")
    return []


# =============================================================================
# Persistence orchestration
# =============================================================================


def apply_extraction(document: Document, extraction: LeaseExtraction) -> Document:
    """Project a validated extraction onto the document row."""
    document.lease_start_date = extraction.lease_start_date
    document.lease_end_date = extraction.lease_end_date
    document.total_land_area_sqm = extraction.total_land_area_sqm
    document.survey_numbers = extraction.survey_numbers or []
    document.extracted_json_data = extraction.raw
    document.extraction_status = (
        ExtractionStatus.EXTRACTED if extraction.is_complete else ExtractionStatus.NEEDS_REVIEW
    )
    document.extraction_confidence = extraction.confidence
    document.extraction_model = extraction.model
    document.extracted_at = utcnow()
    document.extraction_error = "; ".join(extraction.issues) or None
    return document


def extract_document(
    db: Session,
    document: Document,
    *,
    extractor: LeaseExtractor | None = None,
    settings: Settings | None = None,
    actor: str = "system:gemini",
    actor_role: str = "system",
) -> Document:
    """Run extraction for a stored lease deed and persist the outcome.

    Failures are recorded on the document (``FAILED`` + ``extraction_error``) and
    re-raised so the caller/worker can surface them.
    """
    if document.doc_type is not DocumentType.LEASE_DEED:
        raise ExtractionError(
            "Automated extraction is currently supported for lease deeds only.",
            context={"doc_type": document.doc_type.value},
        )

    application = db.get(Application, document.application_id)
    if application is None:
        raise ExtractionError("The document's application no longer exists.")

    document.extraction_status = ExtractionStatus.PROCESSING
    document.extraction_error = None
    db.flush()

    try:
        data = StorageService(settings).get_bytes(document.s3_url)
        extraction = (extractor or GeminiLeaseExtractor(settings=settings)).extract(
            data, document.mime_type or DEFAULT_MIME_TYPE
        )
    except DomainError as exc:
        document.extraction_status = ExtractionStatus.FAILED
        document.extraction_error = exc.message
        db.commit()
        raise
    except Exception as exc:  # unexpected SDK/IO failure must not corrupt state
        document.extraction_status = ExtractionStatus.FAILED
        document.extraction_error = str(exc)
        db.commit()
        raise ExtractionError(f"Lease extraction failed: {exc}") from exc

    apply_extraction(document, extraction)

    AuditService(db).record(
        application=application,
        action=(
            "document.extracted"
            if extraction.is_complete
            else "document.needs_review"
        ),
        actor=actor,
        actor_role=actor_role,
        payload={
            "document_id": str(document.id),
            "doc_type": document.doc_type.value,
            "version": document.version,
            "extraction_status": document.extraction_status.value,
            **extraction.as_payload(),
        },
        commit=False,
    )
    db.commit()
    db.refresh(document)
    return document
