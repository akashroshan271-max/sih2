"""UTC clock helpers.

Every timestamp in VERIFLOW is stored as ``TIMESTAMP WITH TIME ZONE`` in UTC.
SQLite (used by the test suite) silently drops ``tzinfo``; :func:`as_utc`
re-attaches UTC so comparisons and audit hashes stay stable across backends.
"""

from __future__ import annotations

from datetime import UTC, datetime


def utcnow() -> datetime:
    """Timezone-aware current UTC time (microsecond precision)."""
    return datetime.now(UTC)


def as_utc(value: datetime) -> datetime:
    """Treat naive datetimes as UTC, convert aware ones to UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def isoformat_utc(value: datetime) -> str:
    """Stable, hash-safe representation: ``2026-07-01T09:30:00.000000+00:00``."""
    return as_utc(value).isoformat(timespec="microseconds")


def days_since(value: datetime, *, now: datetime | None = None) -> float:
    """Fractional days between ``value`` and ``now`` (defaults to current UTC)."""
    return ((now or utcnow()) - as_utc(value)).total_seconds() / 86_400
