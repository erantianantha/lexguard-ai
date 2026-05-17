"""
Google Cloud Storage Service for LexGuard.
Stores uploaded files in GCS; falls back to local filesystem if GCS is not configured.
"""
import logging
import os
from pathlib import Path
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class CloudStorageService:
    """
    Wraps Google Cloud Storage.
    Auto-detects whether GCS is available (GOOGLE_CLOUD_BUCKET env var set
    and credentials present). Falls back to local filesystem transparently.
    """

    def __init__(self):
        self._client = None
        self._bucket = None
        self._use_gcs = False
        self._bucket_name = settings.GCS_BUCKET_NAME

    def _init(self):
        if self._client is not None:
            return
        if not self._bucket_name:
            logger.info("GCS_BUCKET_NAME not set — using local file storage")
            return
        try:
            from google.cloud import storage
            self._client = storage.Client()
            self._bucket = self._client.bucket(self._bucket_name)
            self._use_gcs = True
            logger.info(f"✅ Connected to GCS bucket: {self._bucket_name}")
        except Exception as e:
            logger.warning(f"GCS unavailable ({e}) — using local file storage")
            self._client = None
            self._use_gcs = False

    async def upload_file(self, local_path: str, doc_id: str, filename: str) -> str:
        """
        Upload a file and return its access path/URI.
        Returns GCS blob name if GCS is enabled, otherwise the local path.
        """
        self._init()
        if self._use_gcs and self._bucket:
            blob_name = f"uploads/{doc_id}/{filename}"
            try:
                blob = self._bucket.blob(blob_name)
                blob.upload_from_filename(local_path)
                logger.info(f"Uploaded to GCS: gs://{self._bucket_name}/{blob_name}")
                return f"gs://{self._bucket_name}/{blob_name}"
            except Exception as e:
                logger.error(f"GCS upload failed ({e}), using local path")
        return local_path

    async def download_to_local(self, gcs_uri: str, local_path: str) -> str:
        """
        Download a GCS file to a local temp path for processing.
        If already local path, returns as-is.
        """
        if not gcs_uri.startswith("gs://"):
            return gcs_uri  # already local

        self._init()
        if not self._use_gcs or not self._bucket:
            raise RuntimeError(f"Cannot access GCS file {gcs_uri}: GCS not configured")

        try:
            # Parse bucket/blob from gs:// URI
            parts = gcs_uri[5:].split("/", 1)
            blob_name = parts[1] if len(parts) > 1 else ""
            blob = self._bucket.blob(blob_name)
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            blob.download_to_filename(local_path)
            logger.info(f"Downloaded from GCS: {gcs_uri} → {local_path}")
            return local_path
        except Exception as e:
            raise RuntimeError(f"GCS download failed: {e}")

    async def delete_file(self, file_ref: str) -> bool:
        """Delete a file from GCS or local filesystem."""
        if file_ref.startswith("gs://"):
            self._init()
            if self._use_gcs and self._bucket:
                try:
                    parts = file_ref[5:].split("/", 1)
                    blob_name = parts[1] if len(parts) > 1 else ""
                    self._bucket.blob(blob_name).delete()
                    return True
                except Exception as e:
                    logger.error(f"GCS delete failed: {e}")
                    return False
        else:
            if os.path.exists(file_ref):
                os.remove(file_ref)
                return True
        return False

    @property
    def is_gcs_enabled(self) -> bool:
        self._init()
        return self._use_gcs


gcs_service = CloudStorageService()
