"""SHA-256 hash chain primitives for the audit trail.

Each :class:`~app.models.AuditLog` row stores

    sha256_hash = SHA256(canonical_json(core_fields, previous_hash))

where ``canonical_json`` sorts keys and uses compact separators, so the digest
is reproducible from the row alone. Chaining the previous digest makes silent
deletion, reordering or editing of history detectable by re-walking the chain:

    GENESIS <- h1 <- h2 <- h3

Verification recomputes every digest from the stored fields, so a forged row
would have to rewrite every subsequent entry as well.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any, Protocol

from app.core.time import isoformat_utc

#: Sentinel previous-hash for the first entry of an application's chain.
GENESIS_HASH: str = "0" * 64


def _json_default(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serialisable")


def canonical_json(payload: Any) -> str:
    """Deterministic JSON: sorted keys, compact separators, UTF-8 friendly."""
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=_json_default,
    )


def _status_value(value: Enum | str | None) -> str | None:
    if value is None:
        return None
    return value.value if isinstance(value, Enum) else str(value)


def build_hash_input(
    *,
    application_id: uuid.UUID | str,
    action: str,
    actor: str,
    timestamp: datetime,
    from_status: Enum | str | None = None,
    to_status: Enum | str | None = None,
    payload: dict[str, Any] | None = None,
    previous_hash: str | None = None,
) -> str:
    """Canonical string that is hashed for an audit entry."""
    return canonical_json(
        {
            "application_id": str(application_id),
            "action": action,
            "actor": actor,
            "timestamp": isoformat_utc(timestamp),
            "from_status": _status_value(from_status),
            "to_status": _status_value(to_status),
            "payload": payload or {},
            "previous_hash": previous_hash or GENESIS_HASH,
        }
    )


def compute_audit_hash(**kwargs: Any) -> str:
    """SHA-256 hex digest over the canonical audit payload."""
    return hashlib.sha256(build_hash_input(**kwargs).encode("utf-8")).hexdigest()


def sha256_bytes(data: bytes) -> str:
    """Digest used for uploaded-file integrity (``Document.content_sha256``)."""
    return hashlib.sha256(data).hexdigest()


class AuditEntryLike(Protocol):
    """Minimal shape shared by ORM rows and plain objects in tests."""

    application_id: Any
    id: Any
    action: str
    actor: str
    from_status: Any
    to_status: Any
    payload: dict[str, Any] | None
    timestamp: datetime
    sha256_hash: str
    previous_hash: str | None


@dataclass(frozen=True)
class ChainVerification:
    """Outcome of re-walking an application's audit chain."""

    valid: bool
    checked: int
    broken_at: int | None = None
    entry_id: str | None = None
    expected_hash: str | None = None
    stored_hash: str | None = None
    reason: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "checked": self.checked,
            "broken_at": self.broken_at,
            "entry_id": self.entry_id,
            "expected_hash": self.expected_hash,
            "stored_hash": self.stored_hash,
            "reason": self.reason,
        }


def verify_chain(entries: Sequence[AuditEntryLike]) -> ChainVerification:
    """Recompute every digest and link; entries must be in chain order."""
    previous_hash: str | None = None

    for index, entry in enumerate(entries):
        if index == 0:
            if entry.previous_hash not in (None, GENESIS_HASH):
                return ChainVerification(
                    valid=False,
                    checked=index,
                    broken_at=index,
                    entry_id=str(entry.id),
                    stored_hash=entry.previous_hash,
                    reason="genesis entry references a predecessor",
                )
        elif entry.previous_hash != previous_hash:
            return ChainVerification(
                valid=False,
                checked=index,
                broken_at=index,
                entry_id=str(entry.id),
                expected_hash=previous_hash,
                stored_hash=entry.previous_hash,
                reason="previous_hash does not match the preceding entry",
            )

        expected = compute_audit_hash(
            application_id=entry.application_id,
            action=entry.action,
            actor=entry.actor,
            timestamp=entry.timestamp,
            from_status=entry.from_status,
            to_status=entry.to_status,
            payload=entry.payload,
            previous_hash=entry.previous_hash,
        )
        if expected != entry.sha256_hash:
            return ChainVerification(
                valid=False,
                checked=index,
                broken_at=index,
                entry_id=str(entry.id),
                expected_hash=expected,
                stored_hash=entry.sha256_hash,
                reason="sha256_hash does not match the entry contents",
            )

        previous_hash = entry.sha256_hash

    return ChainVerification(valid=True, checked=len(entries))
