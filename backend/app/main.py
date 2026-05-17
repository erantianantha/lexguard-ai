"""
LexGuard FastAPI Application — Main entry point.
Production-ready: Cloud Run compatible, dynamic settings, no hardcoded values.
"""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.core.config import settings
from app.api.endpoints.documents import router as documents_router
from app.services.database import db_service
from app.api.endpoints import documents as doc_module

# ── Logging ──────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ── Lifecycle ────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle — startup and shutdown."""
    logger.info(f"🛡️  Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    await db_service.initialize()
    logger.info(f"📦 Database backend: {db_service.backend}")
    logger.info(f"🤖 LLM provider: {settings.resolved_llm_provider() or 'NOT CONFIGURED'}")

    # Log Google Cloud service availability
    if settings.GOOGLE_CLOUD_PROJECT:
        logger.info(f"☁️  Google Cloud Project: {settings.GOOGLE_CLOUD_PROJECT}")
        try:
            from app.services.vertex_service import vertex_service
            logger.info(f"   Vertex AI: {'✅' if vertex_service.is_available else '⚠️  unavailable'}")
        except Exception:
            pass
        try:
            from app.services.vision_service import vision_service
            logger.info(f"   Cloud Vision: {'✅' if vision_service.is_available else '⚠️  unavailable'}")
        except Exception:
            pass
        try:
            from app.services.gcs_service import gcs_service
            logger.info(f"   Cloud Storage: {'✅ ' + settings.GCS_BUCKET_NAME if gcs_service.is_gcs_enabled else '⚠️  no bucket configured'}")
        except Exception:
            pass
    else:
        logger.info("☁️  Google Cloud: not configured (set GOOGLE_CLOUD_PROJECT to enable Vertex AI + GCS + Firestore)")

    yield
    logger.info("Shutting down LexGuard")


# ── App ──────────────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    description="AI-powered contract analysis platform.",
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Dynamic CORS: accept everything in dev, locked-down in prod via env var
_cors_origins = settings.CORS_ORIGINS or ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────
app.include_router(documents_router, prefix=settings.API_PREFIX)


# ── Settings endpoints ────────────────────────────────────────
class SettingsUpdate(BaseModel):
    api_key: str
    provider: str = "gemini"


@app.get("/api/v1/settings")
async def get_settings():
    """Return current (non-secret) configuration and Google Cloud status."""
    from app.services.vision_service import vision_service
    from app.services.gcs_service import gcs_service
    from app.services.vertex_service import vertex_service

    provider = settings.resolved_llm_provider()
    return {
        "provider": provider or settings.LLM_PROVIDER,
        "model": (
            settings.GEMINI_MODEL if provider == "gemini"
            else settings.VERTEX_MODEL if provider == "vertex"
            else settings.OPENROUTER_MODEL
        ),
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
            "firestore_collection": settings.FIRESTORE_COLLECTION if settings.GOOGLE_CLOUD_PROJECT else None,
        },
        "supported_formats": settings.ALLOWED_EXTENSIONS,
        "database_backend": db_service.backend,
    }


@app.post("/api/v1/settings")
async def update_settings(update: SettingsUpdate):
    """
    Hot-update API key + provider at runtime.
    Also writes to .env (persists across restarts in non-Cloud environments).
    On Cloud Run, use Secret Manager — this endpoint still updates in-memory.
    """
    provider = update.provider.lower()
    if provider not in ("gemini", "openrouter"):
        from fastapi import HTTPException
        raise HTTPException(400, "provider must be 'gemini' or 'openrouter'")

    # Update in-memory config (immediate effect, no restart needed)
    if provider == "gemini":
        settings.GEMINI_API_KEY = update.api_key
        settings.LLM_PROVIDER = "gemini"
    else:
        settings.OPENROUTER_API_KEY = update.api_key
        settings.LLM_PROVIDER = "openrouter"

    # Also refresh the pipeline's analysis engine so next analysis uses new key
    doc_module.pipeline.analysis_engine._gemini_client = None  # force re-init
    if provider == "gemini":
        doc_module.pipeline.analysis_engine.model = settings.GEMINI_MODEL
    else:
        doc_module.pipeline.analysis_engine.model = settings.OPENROUTER_MODEL

    # Persist to .env file (local dev / persistent VMs only — skipped if file missing)
    env_path = os.environ.get("ENV_FILE_PATH", ".env")
    try:
        lines = []
        if os.path.exists(env_path):
            with open(env_path, "r") as f:
                lines = f.readlines()

        key_name = f"{provider.upper()}_API_KEY"
        updated_lines = []
        key_written = False
        provider_written = False

        for line in lines:
            if line.startswith(f"{key_name}="):
                updated_lines.append(f"{key_name}={update.api_key}\n")
                key_written = True
            elif line.startswith("LLM_PROVIDER="):
                updated_lines.append(f"LLM_PROVIDER={provider}\n")
                provider_written = True
            else:
                updated_lines.append(line)

        if not key_written:
            updated_lines.append(f"{key_name}={update.api_key}\n")
        if not provider_written:
            updated_lines.append(f"LLM_PROVIDER={provider}\n")

        with open(env_path, "w") as f:
            f.writelines(updated_lines)

        logger.info(f"Settings saved to {env_path}: provider={provider}")
    except OSError as e:
        logger.warning(f"Could not write .env (read-only FS, expected on Cloud Run): {e}")

    return {
        "status": "success",
        "provider": provider,
        "configured": settings.llm_is_configured(),
        "message": f"API key and provider updated to '{provider}'",
    }


# ── Health & Root ─────────────────────────────────────────────
@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "operational",
        "llm_provider": settings.resolved_llm_provider() or "not configured",
        "llm_configured": settings.llm_is_configured(),
    }


@app.get("/health")
async def health():
    """Cloud Run health check — always returns 200 quickly."""
    return {"status": "healthy", "service": settings.APP_NAME}
