"""
LexGuard FastAPI Application — Main entry point.
Production-ready: Cloud Run compatible, security headers, dynamic settings.
"""
from __future__ import annotations

import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from app.api.endpoints import documents as doc_module
from app.api.endpoints.documents import router as documents_router
from app.core.config import settings
from app.services.database import db_service
from app.utils.security import validate_api_key_format

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
VALID_PROVIDERS = frozenset({"gemini", "openrouter"})
SECURITY_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
}


# ── Lifecycle ─────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    """Application lifecycle — startup and shutdown hooks."""
    logger.info("🛡️  Starting %s v%s", settings.APP_NAME, settings.APP_VERSION)

    await db_service.initialize()
    logger.info("📦 Database backend: %s", db_service.backend)

    provider = settings.resolved_llm_provider()
    logger.info("🤖 LLM provider: %s", provider or "NOT CONFIGURED")

    if settings.GOOGLE_CLOUD_PROJECT:
        logger.info("☁️  Google Cloud Project: %s", settings.GOOGLE_CLOUD_PROJECT)
        _log_gcp_services()
    else:
        logger.info(
            "☁️  Google Cloud: not configured "
            "(set GOOGLE_CLOUD_PROJECT to enable Vertex AI + GCS + Firestore)"
        )

    yield

    logger.info("🛑 Shutting down %s", settings.APP_NAME)


def _log_gcp_services() -> None:
    """Log availability of each Google Cloud service at startup."""
    service_checks = [
        ("app.services.vertex_service", "vertex_service", "is_available", "Vertex AI"),
        ("app.services.vision_service", "vision_service", "is_available", "Cloud Vision"),
        ("app.services.gcs_service", "gcs_service", "is_gcs_enabled", "Cloud Storage"),
    ]
    for module_path, attr_name, flag_attr, label in service_checks:
        try:
            import importlib
            mod = importlib.import_module(module_path)
            svc = getattr(mod, attr_name)
            available = getattr(svc, flag_attr, False)
            status = "✅" if available else "⚠️  unavailable"
            logger.info("   %s: %s", label, status)
        except Exception:  # noqa: BLE001
            logger.debug("   %s: could not check status", label)


# ── App factory ───────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "LexGuard AI — Production-grade contract intelligence platform. "
        "Upload any contract, get instant risk analysis, chat with your AI Lawyer."
    ),
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
)

# ── Security headers middleware ───────────────────────────────────────────────
@app.middleware("http")
async def add_security_headers(request: Request, call_next) -> Response:
    """Inject security headers on every response."""
    start = time.perf_counter()
    response: Response = await call_next(request)
    for header, value in SECURITY_HEADERS.items():
        response.headers[header] = value
    response.headers["X-Response-Time"] = f"{(time.perf_counter() - start) * 1000:.1f}ms"
    return response


# ── CORS ──────────────────────────────────────────────────────────────────────
_cors_origins: list[str] = settings.CORS_ORIGINS or ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
)

# ── Global exception handler ──────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all: log unexpected errors without leaking stack traces to clients."""
    logger.error("Unhandled exception on %s %s: %s", request.method, request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred. Please try again."},
    )


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(documents_router, prefix=settings.API_PREFIX)


# ── Settings schema ───────────────────────────────────────────────────────────
class SettingsUpdate(BaseModel):
    """Request body for updating LLM provider credentials."""

    api_key: str = Field(..., min_length=20, max_length=500, description="LLM API key")
    provider: str = Field("gemini", description="LLM provider: 'gemini' or 'openrouter'")

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        """Ensure provider is a known value."""
        v = v.lower().strip()
        if v not in VALID_PROVIDERS:
            raise ValueError(f"provider must be one of: {', '.join(sorted(VALID_PROVIDERS))}")
        return v

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        """Strip whitespace from key."""
        return v.strip()


# ── Settings endpoints ────────────────────────────────────────────────────────
@app.get(
    "/api/v1/settings",
    summary="Get current configuration",
    response_description="Non-secret configuration and Google Cloud service status",
)
async def get_settings() -> dict[str, Any]:
    """Return current (non-secret) configuration and Google Cloud service status."""
    from app.services.gcs_service import gcs_service
    from app.services.vertex_service import vertex_service
    from app.services.vision_service import vision_service

    provider = settings.resolved_llm_provider()
    model_map = {
        "gemini": settings.GEMINI_MODEL,
        "vertex": settings.VERTEX_MODEL,
        "openrouter": settings.OPENROUTER_MODEL,
    }

    return {
        "provider": provider or settings.LLM_PROVIDER,
        "model": model_map.get(provider, settings.OPENROUTER_MODEL),
        "configured": settings.llm_is_configured(),
        "gemini_key_set": bool(settings.GEMINI_API_KEY),
        "openrouter_key_set": bool(settings.OPENROUTER_API_KEY),
        "google_cloud": {
            "project": settings.GOOGLE_CLOUD_PROJECT or None,
            "region": settings.GOOGLE_CLOUD_REGION,
            "vertex_ai": vertex_service.is_available,
            "cloud_vision": vision_service.is_available,
            "cloud_storage": gcs_service.is_gcs_enabled,
            "gcs_bucket": settings.GCS_BUCKET_NAME or None,
            "firestore_collection": (
                settings.FIRESTORE_COLLECTION if settings.GOOGLE_CLOUD_PROJECT else None
            ),
        },
        "supported_formats": settings.ALLOWED_EXTENSIONS,
        "database_backend": db_service.backend,
    }


@app.post(
    "/api/v1/settings",
    summary="Update API key and provider",
    response_description="Confirmation of updated configuration",
)
async def update_settings(update: SettingsUpdate) -> dict[str, Any]:
    """
    Hot-update API key and provider at runtime.

    Changes take effect immediately with no restart required.
    Also persists to .env on local/VM deployments.
    On Cloud Run, environment variables should be managed via Secret Manager.
    """
    from fastapi import HTTPException

    provider = update.provider  # already validated by Pydantic

    # Format-validate the API key for the given provider
    ok, msg = validate_api_key_format(provider, update.api_key)
    if not ok:
        raise HTTPException(status_code=400, detail=f"Invalid API key: {msg}")

    # Update in-memory config (immediate effect)
    if provider == "gemini":
        settings.GEMINI_API_KEY = update.api_key
        settings.LLM_PROVIDER = "gemini"
    else:
        settings.OPENROUTER_API_KEY = update.api_key
        settings.LLM_PROVIDER = "openrouter"

    # Refresh the pipeline's engine so the next analysis picks up the new key
    doc_module.pipeline.analysis_engine._gemini_client = None
    doc_module.pipeline.analysis_engine.model = (
        settings.GEMINI_MODEL if provider == "gemini" else settings.OPENROUTER_MODEL
    )

    # Persist to .env (local dev / persistent VMs; skipped on read-only Cloud Run FS)
    _persist_to_env(provider, update.api_key)

    logger.info("Settings updated: provider=%s", provider)
    return {
        "status": "success",
        "provider": provider,
        "configured": settings.llm_is_configured(),
        "message": f"API key updated for provider '{provider}'.",
    }


def _persist_to_env(provider: str, api_key: str) -> None:
    """Write updated key to .env file. Silently skips on read-only filesystems."""
    env_path = os.environ.get("ENV_FILE_PATH", ".env")
    key_name = f"{provider.upper()}_API_KEY"
    try:
        lines: list[str] = []
        if os.path.exists(env_path):
            with open(env_path, encoding="utf-8") as fh:
                lines = fh.readlines()

        updated: list[str] = []
        key_written = provider_written = False
        for line in lines:
            if line.startswith(f"{key_name}="):
                updated.append(f"{key_name}={api_key}\n")
                key_written = True
            elif line.startswith("LLM_PROVIDER="):
                updated.append(f"LLM_PROVIDER={provider}\n")
                provider_written = True
            else:
                updated.append(line)
        if not key_written:
            updated.append(f"{key_name}={api_key}\n")
        if not provider_written:
            updated.append(f"LLM_PROVIDER={provider}\n")

        with open(env_path, "w", encoding="utf-8") as fh:
            fh.writelines(updated)

        logger.info("Persisted settings to %s", env_path)
    except OSError as exc:
        logger.warning("Could not write .env (read-only FS — expected on Cloud Run): %s", exc)


# ── Health & Root ─────────────────────────────────────────────────────────────
@app.get("/", include_in_schema=False)
async def root() -> dict[str, Any]:
    """Root endpoint — basic service info."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "operational",
        "llm_provider": settings.resolved_llm_provider() or "not configured",
        "llm_configured": settings.llm_is_configured(),
        "docs": "/docs" if settings.DEBUG else "disabled in production",
    }


@app.get("/health", summary="Health check", response_description="Service health status")
async def health() -> dict[str, str]:
    """
    Cloud Run / Render health check endpoint.

    Returns 200 immediately. Used by load balancers to determine instance readiness.
    """
    return {"status": "healthy", "service": settings.APP_NAME, "version": settings.APP_VERSION}
