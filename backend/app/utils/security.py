"""
LexGuard Security & Validation Utilities.

Provides:
- File magic-byte signature validation
- Filename sanitisation with path-traversal protection
- API key format validation
- Sliding-window rate limiter
- Log-injection prevention
"""
from __future__ import annotations

import logging
import re
import time
from collections import defaultdict
from pathlib import Path
from threading import Lock
from typing import Final

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

MAX_FILENAME_LEN: Final[int] = 255
MAX_STEM_LEN: Final[int] = 200
MIN_API_KEY_LEN: Final[int] = 20
MAX_API_KEY_LEN: Final[int] = 500
MAX_DOCUMENT_ID_LEN: Final[int] = 64

# Characters allowed in sanitised filenames
_SAFE_FILENAME_RE: Final[re.Pattern[str]] = re.compile(r"[^a-zA-Z0-9_.\-]")

# Characters that must not appear in log output (log-injection prevention)
_LOG_INJECTION_RE: Final[re.Pattern[str]] = re.compile(r"[\r\n\x00-\x1f]")

# Magic-byte file signatures for format verification
MAGIC_BYTES: Final[dict[str, list[bytes]]] = {
    ".pdf":  [b"%PDF"],
    ".docx": [b"PK\x03\x04"],   # ZIP-based (Office Open XML)
    ".xlsx": [b"PK\x03\x04"],   # ZIP-based (Office Open XML)
    ".xls":  [b"\xd0\xcf\x11\xe0"],  # Compound Document (OLE2)
    ".jpg":  [b"\xff\xd8\xff"],
    ".jpeg": [b"\xff\xd8\xff"],
    ".png":  [b"\x89PNG"],
    ".rtf":  [b"{\\rtf"],
    # .txt and .csv have no reliable magic bytes — skip check
}

# Provider-specific API key prefix hints (soft validation only)
_API_KEY_PREFIXES: Final[dict[str, str]] = {
    "gemini": "AIza",
    "openrouter": "sk-or-",
}


# ── File Security ─────────────────────────────────────────────────────────────

def sanitise_filename(name: str) -> str:
    """
    Return a safe filename, stripping directory components and unsafe characters.

    Protection against:
    - Path traversal (``../``, ``/``, Windows backslashes)
    - Null bytes and control characters
    - Filenames that exceed OS limits

    Args:
        name: Raw filename from the client.

    Returns:
        A sanitised filename safe for use on the local filesystem.
    """
    # Extract the base name, discarding any directory prefix
    safe = Path(name).name
    # Replace all non-allowlisted characters with underscores
    safe = _SAFE_FILENAME_RE.sub("_", safe)
    # Enforce maximum length while preserving the file extension
    if len(safe) > MAX_FILENAME_LEN:
        stem = Path(safe).stem[:MAX_STEM_LEN]
        suffix = Path(safe).suffix[:20]  # cap extension too
        safe = stem + suffix
    return safe or "upload"


def validate_file_magic(content: bytes, ext: str) -> bool:
    """
    Verify that file content matches the declared extension's magic bytes.

    Args:
        content: Raw file bytes (at least the first 8 bytes are sufficient).
        ext: File extension including leading dot, e.g. ``.pdf``.

    Returns:
        ``True`` if the content matches a known signature or no check is needed.
        ``False`` if the content does not match, indicating a likely spoofed file.
    """
    signatures = MAGIC_BYTES.get(ext.lower())
    if signatures is None:
        # No signature defined for this type — allow (e.g. .txt, .csv)
        return True
    return any(content[: len(sig)] == sig for sig in signatures)


def validate_document_id(document_id: str) -> bool:
    """
    Return True if *document_id* is a valid, safe document identifier.

    Accepts only alphanumeric characters up to ``MAX_DOCUMENT_ID_LEN`` chars.
    This prevents path traversal and injection attacks in database queries.

    Args:
        document_id: The document ID string to validate.

    Returns:
        ``True`` if the ID is safe to use, ``False`` otherwise.
    """
    return bool(document_id) and document_id.isalnum() and len(document_id) <= MAX_DOCUMENT_ID_LEN


def sanitise_log_value(value: str, max_len: int = 200) -> str:
    """
    Remove control characters from a value before writing it to logs.

    Prevents log-injection attacks where a crafted filename could insert
    fake log lines.

    Args:
        value: The string to sanitise.
        max_len: Maximum length to include in the log output.

    Returns:
        A log-safe version of *value*, truncated to *max_len*.
    """
    clean = _LOG_INJECTION_RE.sub("_", value)
    return clean[:max_len]


# ── API Key Validation ────────────────────────────────────────────────────────

def validate_api_key_format(provider: str, key: str) -> tuple[bool, str]:
    """
    Perform lightweight format validation on an API key.

    This is a UX guard only — not a cryptographic check.
    The key is accepted as long as it passes length bounds.
    Prefix mismatches produce a debug warning but do not reject the key.

    Args:
        provider: LLM provider name, e.g. ``"gemini"`` or ``"openrouter"``.
        key: The API key string (already stripped of whitespace).

    Returns:
        A ``(valid: bool, message: str)`` tuple.
    """
    if not key:
        return False, "API key cannot be empty."
    if len(key) < MIN_API_KEY_LEN:
        return False, f"API key appears too short (minimum {MIN_API_KEY_LEN} characters)."
    if len(key) > MAX_API_KEY_LEN:
        return False, f"API key appears too long (maximum {MAX_API_KEY_LEN} characters)."

    expected_prefix = _API_KEY_PREFIXES.get(provider.lower())
    if expected_prefix and not key.startswith(expected_prefix):
        logger.debug(
            "API key for provider '%s' does not start with expected prefix '%s' — still accepted.",
            provider,
            expected_prefix,
        )

    return True, "ok"


# ── Rate Limiter ──────────────────────────────────────────────────────────────

class RateLimiter:
    """
    Thread-safe sliding-window rate limiter keyed by an arbitrary client ID.

    Uses a lock to protect concurrent access in an async + threaded environment.
    Timestamps outside the current window are pruned on every check.

    Args:
        max_requests: Maximum number of requests allowed per *window_seconds*.
        window_seconds: Length of the sliding time window in seconds.
    """

    def __init__(self, max_requests: int = 20, window_seconds: int = 60) -> None:
        self._max = max_requests
        self._window = window_seconds
        self._store: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def is_allowed(self, client_id: str) -> bool:
        """
        Return ``True`` if the client has not exceeded the rate limit.

        Prunes expired timestamps before checking to maintain the sliding window.

        Args:
            client_id: Arbitrary string identifying the client (e.g. IP address).

        Returns:
            ``True`` if the request is within the allowed rate, ``False`` if limited.
        """
        now = time.monotonic()
        cutoff = now - self._window
        with self._lock:
            timestamps = self._store[client_id]
            # Prune expired timestamps in-place
            self._store[client_id] = [t for t in timestamps if t > cutoff]
            if len(self._store[client_id]) >= self._max:
                return False
            self._store[client_id].append(now)
        return True

    def reset(self, client_id: str) -> None:
        """
        Clear all recorded timestamps for *client_id*.

        Primarily used in tests to reset state between test cases.

        Args:
            client_id: The client whose rate-limit window should be cleared.
        """
        with self._lock:
            self._store.pop(client_id, None)

    def remaining(self, client_id: str) -> int:
        """
        Return the number of remaining allowed requests in the current window.

        Args:
            client_id: The client to query.

        Returns:
            Non-negative integer representing remaining capacity.
        """
        now = time.monotonic()
        cutoff = now - self._window
        with self._lock:
            count = sum(1 for t in self._store.get(client_id, []) if t > cutoff)
        return max(0, self._max - count)


# ── Singleton rate limiters ───────────────────────────────────────────────────

#: 30 uploads per 10 minutes per IP
upload_rate_limiter: Final[RateLimiter] = RateLimiter(max_requests=30, window_seconds=600)

#: 60 chat messages per minute per IP
chat_rate_limiter: Final[RateLimiter] = RateLimiter(max_requests=60, window_seconds=60)
