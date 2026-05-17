"""
LexGuard Configuration — Full Google Cloud + multi-provider settings.
All values overridable via environment variables.
"""
import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):

    # ── Application ────────────────────────────────────────────────────────
    APP_NAME: str = "LexGuard"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    API_PREFIX: str = "/api/v1"

    # ── Server ─────────────────────────────────────────────────────────────
    HOST: str = "0.0.0.0"
    PORT: int = 8080

    # ── CORS ───────────────────────────────────────────────────────────────
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://localhost:8080",
        "*",
    ]

    # ── LLM Provider ───────────────────────────────────────────────────────
    # Priority: "auto" tries vertex → gemini → openrouter
    LLM_PROVIDER: str = "auto"
    LLM_MAX_TOKENS: int = 8192

    # OpenRouter
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "google/gemini-2.0-flash-001"
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_SITE_URL: str = "https://lexguard.app"
    OPENROUTER_EMBEDDING_MODEL: str = "openai/text-embedding-3-small"

    # Google Gemini (direct API)
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"

    # ── Google Cloud ───────────────────────────────────────────────────────
    GOOGLE_CLOUD_PROJECT: str = ""       # e.g. "lexguard-prod"
    GOOGLE_CLOUD_REGION: str = "us-central1"
    GOOGLE_APPLICATION_CREDENTIALS: str = ""  # path to SA key JSON

    # Vertex AI
    VERTEX_MODEL: str = "gemini-2.0-flash"
    VERTEX_EMBED_MODEL: str = "textembedding-gecko@003"

    # Cloud Storage
    GCS_BUCKET_NAME: str = ""            # e.g. "lexguard-uploads"

    # Firestore
    FIRESTORE_COLLECTION: str = "lexguard_documents"

    # Cloud Vision
    VISION_ENABLED: bool = True          # set False to always use Tesseract

    # ── MongoDB (fallback if Firestore not configured) ──────────────────────
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "lexguard"

    # ── File Upload ────────────────────────────────────────────────────────
    MAX_FILE_SIZE_MB: int = 50
    UPLOAD_DIR: str = "/tmp/uploads"
    ALLOWED_EXTENSIONS: list[str] = [
        ".pdf", ".docx", ".xlsx", ".xls",
        ".txt", ".csv", ".rtf",
        ".jpg", ".jpeg", ".png",
    ]

    # ── Processing ─────────────────────────────────────────────────────────
    CHUNK_SIZE_TOKENS: int = 500
    CHUNK_OVERLAP_TOKENS: int = 50
    RAG_ENABLED: bool = True

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"

    # ── Provider Resolution ────────────────────────────────────────────────

    def resolved_llm_provider(self) -> str:
        """
        Resolve which LLM backend to use.
        Priority: vertex → gemini → openrouter (in 'auto' mode)
        """
        provider = (self.LLM_PROVIDER or "auto").lower()
        if provider == "vertex":
            return "vertex"
        if provider == "gemini":
            return "gemini"
        if provider == "openrouter":
            return "openrouter"
        # auto mode: prefer vertex (no key needed on Cloud Run)
        if provider == "auto":
            if self.GOOGLE_CLOUD_PROJECT:
                return "vertex"
            if self.GEMINI_API_KEY:
                return "gemini"
            if self.OPENROUTER_API_KEY:
                return "openrouter"
        return ""

    def llm_is_configured(self) -> bool:
        provider = self.resolved_llm_provider()
        if provider == "vertex":
            return bool(self.GOOGLE_CLOUD_PROJECT)
        if provider == "gemini":
            return bool(self.GEMINI_API_KEY)
        if provider == "openrouter":
            return bool(self.OPENROUTER_API_KEY)
        return False


settings = Settings()
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

# Set Google credentials from env if provided
if settings.GOOGLE_APPLICATION_CREDENTIALS:
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.GOOGLE_APPLICATION_CREDENTIALS
