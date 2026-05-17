"""
LexGuard Security & Validation Utilities.
Handles file validation, input sanitisation, and rate-limiting helpers.
"""
import hashlib
import hmac
import logging
import re
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── File Security ─────────────────────────────────────────────────────────────

ALLOWED_MIME_TYPES = {
    ".pdf":  ["application/pdf"],
    ".docx": ["application/vnd.openxmlformats-officedocument.wordprocessingml.document"],
    ".xlsx": ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"],
    ".txt":  ["text/plain", "application/octet-stream"],
    ".jpg":  ["image/jpeg"],
    ".jpeg": ["image/jpeg"],
    ".png":  ["image/png"],
}

# Magic bytes (file signatures) for common formats
MAGIC_BYTES: dict[str, list[bytes]] = {
    ".pdf":  [b"%PDF"],
    ".docx": [b"PK\x03\x04"],   # ZIP-based
    ".xlsx": [b"PK\x03\x04"],
    ".jpg":  [b"\xff\xd8\xff"],
    ".jpeg": [b"\xff\xd8\xff"],
    ".png":  [b"\x89PNG"],
}

MAX_FILENAME_LEN = 255
SAFE_FILENAME_RE = re.compile(r"[^a-zA-Z0-9_.\-]")


def sanitise_filename(name: str) -> str:
    """Return a safe filename, stripping path traversal and special chars."""
    name = Path(name).name                   # strip any directory prefix
    name = SAFE_FILENAME_RE.sub("_", name)  # replace unsafe chars
    if len(name) > MAX_FILENAME_LEN:
        stem = Path(name).stem[:200]
        suffix = Path(name).suffix
        name = stem + suffix
    return name or "upload"


def validate_file_magic(content: bytes, ext: str) -> bool:
    """Verify file magic bytes match the declared extension."""
    sigs = MAGIC_BYTES.get(ext.lower())
    if sigs is None:
        return True   # No signature check for .txt
    return any(content[:len(sig)] == sig for sig in sigs)


def validate_api_key_format(provider: str, key: str) -> tuple[bool, str]:
    """Basic format validation for API keys (not a security measure, just UX)."""
    key = key.strip()
    if not key:
        return False, "API key cannot be empty."
    if len(key) < 20:
        return False, "API key appears too short."
    if len(key) > 500:
        return False, "API key appears too long."
    if provider == "gemini" and not (key.startswith("AIza") or len(key) == 39):
        # Gemini keys start with AIza and are 39 chars — soft warning only
        logger.debug("Gemini key format unexpected (still accepted)")
    if provider == "openrouter" and not key.startswith("sk-or-"):
        logger.debug("OpenRouter key format unexpected (still accepted)")
    return True, "ok"


# ── Simple In-Memory Rate Limiter ─────────────────────────────────────────────

class RateLimiter:
    """Sliding-window rate limiter keyed by client IP."""

    def __init__(self, max_requests: int = 20, window_seconds: int = 60):
        self._max = max_requests
        self._window = window_seconds
        self._store: dict[str, list[float]] = {}

    def is_allowed(self, client_id: str) -> bool:
        now = time.time()
        bucket = self._store.setdefault(client_id, [])
        # Remove old timestamps
        self._store[client_id] = [t for t in bucket if now - t < self._window]
        if len(self._store[client_id]) >= self._max:
            return False
        self._store[client_id].append(now)
        return True

    def reset(self, client_id: str) -> None:
        self._store.pop(client_id, None)


# Singleton rate limiter: 30 uploads per 10 min per IP
upload_rate_limiter = RateLimiter(max_requests=30, window_seconds=600)
chat_rate_limiter = RateLimiter(max_requests=60, window_seconds=60)
