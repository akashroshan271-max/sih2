"""Typed application settings (12-factor, .env driven)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Identity ----------------------------------------------------------
    project_name: str = "VERIFLOW-AICTE"
    version: str = "0.2.0"
    environment: Literal["development", "test", "staging", "production"] = "development"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"

    # --- Officer sign-in (JWT) ---------------------------------------------
    auth_secret_key: str = "veriflow-dev-only-secret-change-me-in-production"
    auth_token_ttl_minutes: int = Field(default=480, ge=5, le=1440)
    auth_issuer: str = "veriflow-aicte"

    # --- Infrastructure ----------------------------------------------------
    database_url: str = "postgresql+psycopg://veriflow:veriflow@localhost:5432/veriflow"
    redis_url: str = "redis://localhost:6379/0"
    celery_enabled: bool = False
    # ``NoDecode`` keeps pydantic-settings from JSON-decoding the raw env value,
    # so both ``a,b`` and ``["a","b"]`` reach the validator below.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )

    # --- Rule 3: SLA dwell time & hierarchical escalation ------------------
    sla_threshold_days: int = Field(default=15, gt=0)
    escalation_l2_days: int = Field(default=30, gt=0)
    escalation_l3_days: int = Field(default=45, gt=0)

    # --- Gemini ------------------------------------------------------------
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.6-flash"
    gemini_timeout_seconds: float = Field(default=120.0, gt=0)

    # --- Document storage ---------------------------------------------------
    storage_backend: Literal["local", "s3"] = "local"
    local_storage_dir: Path = Path("var/uploads")
    media_url_prefix: str = "/media"
    s3_endpoint_url: str | None = None  # set for MinIO / LocalStack
    s3_bucket: str = "veriflow-aicte-documents"
    s3_region: str = "ap-south-1"
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None
    s3_presign_expiry_seconds: int = 900
    upload_max_bytes: int = 25 * 1024 * 1024
    allowed_upload_mime_types: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: [
            "application/pdf",
            "image/jpeg",
            "image/png",
            "image/webp",
        ]
    )

    @field_validator("cors_origins", "allowed_upload_mime_types", mode="before")
    @classmethod
    def _parse_list(cls, value: object) -> object:
        """Accept ``a,b`` or a JSON array from the environment."""
        if isinstance(value, str):
            raw = value.strip()
            if raw.startswith("["):
                return json.loads(raw)
            return [part.strip() for part in raw.split(",") if part.strip()]
        return value

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    def resolved_upload_dir(self) -> Path:
        """Absolute upload directory for the local storage backend."""
        return self.local_storage_dir.expanduser().resolve()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
