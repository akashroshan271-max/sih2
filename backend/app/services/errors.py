"""Domain errors carrying an API-safe code, message and HTTP status."""

from __future__ import annotations

from typing import Any


class DomainError(Exception):
    """Base class for expected business failures (never a 500)."""

    code: str = "domain_error"
    http_status: int = 400

    def __init__(self, message: str, *, context: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.context = context or {}

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "detail": self.message, "context": self.context}


class Unauthenticated(DomainError):
    """Missing, expired or invalid officer session."""

    code = "unauthenticated"
    http_status = 401


class Forbidden(DomainError):
    """The officer is signed in but their desk does not own this action."""

    code = "forbidden"
    http_status = 403


class NotFoundError(DomainError):
    code = "not_found"
    http_status = 404


class ConflictError(DomainError):
    code = "conflict"
    http_status = 409


class ValidationFailure(DomainError):
    code = "validation_failed"
    http_status = 422


class StorageError(DomainError):
    code = "storage_error"
    http_status = 502


class ExtractionError(DomainError):
    code = "extraction_failed"
    http_status = 422


class AIServiceUnavailable(DomainError):
    code = "ai_service_unavailable"
    http_status = 503
