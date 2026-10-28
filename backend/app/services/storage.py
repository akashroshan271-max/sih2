"""Document storage.

Two interchangeable backends, selected by ``STORAGE_BACKEND``:

* ``local`` — writes under ``var/uploads`` and serves them at ``/media/...``.
  Lets the whole OCR pipeline run in a hackathon demo with no cloud account.
* ``s3`` — AWS S3 or any S3-compatible endpoint (MinIO / LocalStack).

URIs are opaque to callers: ``local://<key>`` or ``s3://<bucket>/<key>``.
"""

from __future__ import annotations

import re
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import Settings, get_settings
from app.core.integrity import sha256_bytes
from app.services.errors import StorageError

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass(frozen=True)
class StoredObject:
    uri: str
    key: str
    size_bytes: int
    sha256: str


def _safe_filename(filename: str) -> str:
    name = Path(filename or "document").name
    cleaned = _SAFE_NAME.sub("_", name).strip("._") or "document"
    return cleaned[:120]


class StorageService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------
    def put(
        self,
        *,
        application_id: uuid.UUID,
        document_id: uuid.UUID,
        filename: str,
        data: bytes,
        mime_type: str,
    ) -> StoredObject:
        key = f"{application_id}/{document_id}-{_safe_filename(filename)}"
        digest = sha256_bytes(data)

        if self.settings.storage_backend == "s3":
            return self._put_s3(key, data, digest, mime_type)

        return self._put_local(key, data, digest)

    def _put_local(self, key: str, data: bytes, digest: str) -> StoredObject:
        path = self.settings.resolved_upload_dir() / key
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        except OSError as exc:  # pragma: no cover - disk/permission failure
            raise StorageError(f"Could not persist document locally: {exc}") from exc
        return StoredObject(uri=f"local://{key}", key=key, size_bytes=len(data), sha256=digest)

    def _put_s3(self, key: str, data: bytes, digest: str, mime_type: str) -> StoredObject:
        client = self._s3_client()
        try:
            client.put_object(
                Bucket=self.settings.s3_bucket,
                Key=key,
                Body=data,
                ContentType=mime_type,
            )
        except Exception as exc:  # boto3 raises many botocore error types
            raise StorageError(f"Could not upload document to S3: {exc}") from exc
        uri = f"s3://{self.settings.s3_bucket}/{key}"
        return StoredObject(uri=uri, key=key, size_bytes=len(data), sha256=digest)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------
    def get_bytes(self, uri: str) -> bytes:
        if uri.startswith("local://"):
            path = self.settings.resolved_upload_dir() / uri.removeprefix("local://")
            try:
                return path.read_bytes()
            except OSError as exc:
                raise StorageError(f"Document not found in local storage: {uri}") from exc

        if uri.startswith("s3://"):
            bucket, _, key = uri.removeprefix("s3://").partition("/")
            try:
                response = self._s3_client().get_object(Bucket=bucket, Key=key)
                return response["Body"].read()
            except Exception as exc:
                raise StorageError(f"Document not found in S3: {uri}") from exc

        raise StorageError(f"Unsupported document URI: {uri}")

    def public_url(self, uri: str) -> str:
        """Browser-openable URL (local backend only; S3 uses presigned URLs)."""
        if uri.startswith("local://"):
            key = uri.removeprefix("local://")
            return f"{self.settings.media_url_prefix}/{key}"
        return uri

    def presigned_url(self, uri: str) -> str:
        if not uri.startswith("s3://"):
            return self.public_url(uri)
        bucket, _, key = uri.removeprefix("s3://").partition("/")
        try:
            return self._s3_client().generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket, "Key": key},
                ExpiresIn=self.settings.s3_presign_expiry_seconds,
            )
        except Exception as exc:  # pragma: no cover
            raise StorageError(f"Could not sign S3 URL: {exc}") from exc

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _s3_client(self) -> Any:
        import boto3

        return boto3.client(
            "s3",
            region_name=self.settings.s3_region,
            endpoint_url=self.settings.s3_endpoint_url,
            aws_access_key_id=self.settings.s3_access_key_id,
            aws_secret_access_key=self.settings.s3_secret_access_key,
        )

    def clear_local(self) -> None:  # pragma: no cover - test helper
        shutil.rmtree(self.settings.resolved_upload_dir(), ignore_errors=True)
