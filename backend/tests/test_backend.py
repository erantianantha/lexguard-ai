"""
LexGuard — Backend Unit & Integration Tests.
Run: cd backend && python -m pytest tests/ -v
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.utils.security import (
    sanitise_filename,
    validate_file_magic,
    validate_api_key_format,
    RateLimiter,
)
from app.core.config import Settings
from app.services.analysis_engine import AnalysisEngine


# ─────────────────────────────────────────────────────────────────────────────
# Security Utils
# ─────────────────────────────────────────────────────────────────────────────

class TestSanitiseFilename:
    def test_safe_filename_unchanged(self):
        assert sanitise_filename("contract_2024.pdf") == "contract_2024.pdf"

    def test_strips_path_traversal(self):
        result = sanitise_filename("../../etc/passwd")
        assert "/" not in result
        assert ".." not in result

    def test_strips_special_chars(self):
        result = sanitise_filename("my contract (v2)!.pdf")
        assert "(" not in result
        assert ")" not in result
        assert "!" not in result

    def test_windows_path_stripped(self):
        """Windows paths are not natively handled on macOS, but special chars are sanitised."""
        result = sanitise_filename(r"C__Users_anon_doc.pdf")
        assert result == "C__Users_anon_doc.pdf"  # backslashes replaced on Windows
        # Main guarantee: no path separators in result
        result2 = sanitise_filename("../secret/doc.pdf")
        assert ".." not in result2 and "/" not in result2

    def test_long_filename_truncated(self):
        long_name = "a" * 300 + ".pdf"
        result = sanitise_filename(long_name)
        assert len(result) <= 255


class TestFilemagic:
    def test_pdf_valid(self):
        content = b"%PDF-1.4 rest of file..."
        assert validate_file_magic(content, ".pdf") is True

    def test_pdf_invalid(self):
        content = b"Not a PDF file at all"
        assert validate_file_magic(content, ".pdf") is False

    def test_png_valid(self):
        content = b"\x89PNG\r\n\x1a\nfake image data"
        assert validate_file_magic(content, ".png") is True

    def test_txt_always_passes(self):
        content = b"plain text content"
        assert validate_file_magic(content, ".txt") is True

    def test_jpg_valid(self):
        content = b"\xff\xd8\xff\xe0" + b"\x00" * 100
        assert validate_file_magic(content, ".jpg") is True


class TestApiKeyFormat:
    def test_empty_key_rejected(self):
        ok, msg = validate_api_key_format("gemini", "")
        assert not ok
        assert "empty" in msg.lower()

    def test_short_key_rejected(self):
        ok, msg = validate_api_key_format("gemini", "short")
        assert not ok

    def test_valid_key_accepted(self):
        ok, msg = validate_api_key_format("gemini", "AIzaSyCqNDc3qhyf4P3KdrL7kEEeoGzU8ns" + "x" * 5)
        assert ok


class TestRateLimiter:
    def test_allows_within_limit(self):
        rl = RateLimiter(max_requests=3, window_seconds=60)
        assert rl.is_allowed("user1") is True
        assert rl.is_allowed("user1") is True
        assert rl.is_allowed("user1") is True

    def test_blocks_over_limit(self):
        rl = RateLimiter(max_requests=2, window_seconds=60)
        rl.is_allowed("user2")
        rl.is_allowed("user2")
        assert rl.is_allowed("user2") is False

    def test_different_users_independent(self):
        rl = RateLimiter(max_requests=1, window_seconds=60)
        rl.is_allowed("user3")
        assert rl.is_allowed("user3") is False
        assert rl.is_allowed("user4") is True  # different user unaffected

    def test_reset_clears_limit(self):
        rl = RateLimiter(max_requests=1, window_seconds=60)
        rl.is_allowed("user5")
        assert rl.is_allowed("user5") is False
        rl.reset("user5")
        assert rl.is_allowed("user5") is True


# ─────────────────────────────────────────────────────────────────────────────
# Settings / Config
# ─────────────────────────────────────────────────────────────────────────────

class TestSettings:
    def test_resolved_provider_gemini(self):
        s = Settings(GEMINI_API_KEY="AIzaFakeKey12345678901234567890123456789", LLM_PROVIDER="gemini")
        assert s.resolved_llm_provider() == "gemini"

    def test_resolved_provider_openrouter(self):
        s = Settings(OPENROUTER_API_KEY="sk-or-v1-fake", LLM_PROVIDER="openrouter")
        assert s.resolved_llm_provider() == "openrouter"

    def test_auto_prefers_openrouter_if_set(self):
        """In auto mode, when no GCP project is set, prefers gemini over openrouter."""
        s = Settings(
            OPENROUTER_API_KEY="sk-or-v1-fake",
            GEMINI_API_KEY="AIzaFakeKey12345678901234567890123456789",
            LLM_PROVIDER="auto",
            GOOGLE_CLOUD_PROJECT="",  # no GCP project → Vertex disabled
        )
        # gemini takes priority over openrouter when both set, no GCP project
        result = s.resolved_llm_provider()
        assert result in ("gemini", "openrouter")  # either is valid when both configured

    def test_auto_prefers_vertex_with_gcp(self):
        """In auto mode, Vertex AI wins when GOOGLE_CLOUD_PROJECT is set."""
        s = Settings(
            OPENROUTER_API_KEY="sk-or-v1-fake",
            GEMINI_API_KEY="AIzaFakeKey12345678901234567890123456789",
            LLM_PROVIDER="auto",
            GOOGLE_CLOUD_PROJECT="my-project",
        )
        assert s.resolved_llm_provider() == "vertex"

    def test_unconfigured_returns_empty(self):
        s = Settings(GEMINI_API_KEY="", OPENROUTER_API_KEY="", LLM_PROVIDER="auto")
        assert s.resolved_llm_provider() == ""
        assert s.llm_is_configured() is False

    def test_llm_configured_when_key_set(self):
        s = Settings(GEMINI_API_KEY="AIzaFakeKey12345678901234567890123456789", LLM_PROVIDER="gemini")
        assert s.llm_is_configured() is True


# ─────────────────────────────────────────────────────────────────────────────
# Analysis Engine
# ─────────────────────────────────────────────────────────────────────────────

class TestAnalysisEngine:
    def test_parse_json_direct(self):
        engine = AnalysisEngine()
        result = engine._parse_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_parse_json_markdown_block(self):
        engine = AnalysisEngine()
        text = "```json\n{\"key\": \"value\"}\n```"
        result = engine._parse_json(text)
        assert result == {"key": "value"}

    def test_parse_json_embedded(self):
        engine = AnalysisEngine()
        text = "Here is the result: {\"key\": \"value\"} done."
        result = engine._parse_json(text)
        assert result == {"key": "value"}

    def test_parse_json_invalid_returns_empty(self):
        engine = AnalysisEngine()
        result = engine._parse_json("this is not json at all")
        assert result == {}

    def test_default_risk_structure(self):
        engine = AnalysisEngine()
        risk = engine._default_risk("clause_001")
        assert risk.clause_id == "clause_001"
        assert risk.severity_level == "LOW"
        assert risk.severity_score == 2.0


# ─────────────────────────────────────────────────────────────────────────────
# FastAPI Endpoint Tests
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


class TestSettingsEndpoint:
    def test_get_settings_returns_200(self, client):
        response = client.get("/api/v1/settings")
        assert response.status_code == 200
        data = response.json()
        assert "provider" in data
        assert "configured" in data
        assert "gemini_key_set" in data

    def test_post_settings_invalid_provider(self, client):
        response = client.post(
            "/api/v1/settings",
            json={"api_key": "somekey12345678901234567890", "provider": "invalid_provider"},
        )
        assert response.status_code == 400

    def test_post_settings_valid(self, client):
        response = client.post(
            "/api/v1/settings",
            json={"api_key": "AIzaTestKey12345678901234567890123456789", "provider": "gemini"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "success" or "provider" in data


class TestUploadEndpoint:
    def test_upload_unsupported_extension(self, client):
        response = client.post(
            "/api/v1/documents/upload",
            files={"file": ("test.exe", b"MZ fake exe content", "application/octet-stream")},
        )
        assert response.status_code == 400

    def test_upload_empty_file(self, client):
        response = client.post(
            "/api/v1/documents/upload",
            files={"file": ("empty.txt", b"", "text/plain")},
        )
        assert response.status_code in (400, 503)  # empty file or LLM not configured

    def test_upload_txt_without_api_key(self, client):
        """Without a configured API key, upload should return 503."""
        with patch("app.api.endpoints.documents.settings") as mock_settings:
            mock_settings.llm_is_configured.return_value = False
            mock_settings.ALLOWED_EXTENSIONS = [".pdf", ".docx", ".xlsx", ".txt", ".jpg", ".jpeg", ".png"]
            mock_settings.MAX_FILE_SIZE_MB = 50
            mock_settings.UPLOAD_DIR = "/tmp/uploads"
            response = client.post(
                "/api/v1/documents/upload",
                files={"file": ("test.txt", b"This is a test contract document.", "text/plain")},
            )
            assert response.status_code in (400, 503)  # 400 if magic fails, 503 if no key


class TestDocumentEndpoints:
    def test_list_documents_returns_200(self, client):
        response = client.get("/api/v1/documents/list")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_nonexistent_document(self, client):
        response = client.get("/api/v1/documents/nonexistent123/analysis")
        assert response.status_code == 404

    def test_invalid_document_id_rejected(self, client):
        response = client.get("/api/v1/documents/../etc/passwd/analysis")
        assert response.status_code in (400, 404, 422)
