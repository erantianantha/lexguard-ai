"""
Vertex AI Service for LexGuard.
Provides:
  - Gemini via Vertex AI SDK (enterprise quota, no API key needed on Cloud Run)
  - Vertex AI Embeddings for RAG
  - Falls back to google-genai direct API if Vertex is unavailable.
"""
import logging
import os
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class VertexAIService:
    """
    Vertex AI integration for LexGuard.
    When running on Cloud Run with a service account, no API key is needed —
    credentials come from Workload Identity / ADC.
    """

    def __init__(self):
        self._initialized = False
        self._model = None
        self._embed_model = None
        self._available = False

    def _init(self):
        if self._initialized:
            return
        self._initialized = True

        project = settings.GOOGLE_CLOUD_PROJECT
        location = settings.GOOGLE_CLOUD_REGION

        if not project:
            logger.info("GOOGLE_CLOUD_PROJECT not set — Vertex AI disabled")
            return

        try:
            import vertexai
            from vertexai.generative_models import GenerativeModel
            vertexai.init(project=project, location=location)
            model_name = settings.VERTEX_MODEL
            self._model = GenerativeModel(model_name)
            self._available = True
            logger.info(f"✅ Vertex AI initialized: project={project}, model={model_name}")
        except Exception as e:
            logger.warning(f"Vertex AI unavailable ({e}) — falling back to direct Gemini API")
            self._available = False

    @property
    def is_available(self) -> bool:
        self._init()
        return self._available

    async def generate(self, system_prompt: str, user_prompt: str, max_tokens: int = 8192) -> str:
        """
        Generate text using Vertex AI Gemini.
        Raises RuntimeError if Vertex AI is not available.
        """
        self._init()
        if not self._available or self._model is None:
            raise RuntimeError("Vertex AI not available")

        try:
            from vertexai.generative_models import GenerationConfig, Part, Content
            import asyncio

            full_prompt = f"{system_prompt}\n\n{user_prompt}"
            config = GenerationConfig(
                max_output_tokens=max_tokens,
                temperature=0.1,
                top_p=0.9,
            )

            # Vertex AI SDK is synchronous — run in thread pool
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self._model.generate_content(
                    full_prompt,
                    generation_config=config,
                    stream=False,
                ),
            )
            text = response.text
            if not text or not text.strip():
                raise ValueError("Empty response from Vertex AI")
            logger.debug(f"Vertex AI response: {len(text)} chars")
            return text

        except Exception as e:
            logger.error(f"Vertex AI generation failed: {e}")
            raise

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """
        Generate text embeddings using Vertex AI textembedding-gecko.
        Falls back to empty list if unavailable.
        """
        self._init()
        if not self._available:
            return []

        try:
            from vertexai.language_models import TextEmbeddingModel
            import asyncio

            embed_model_name = settings.VERTEX_EMBED_MODEL
            loop = asyncio.get_event_loop()

            def _embed():
                model = TextEmbeddingModel.from_pretrained(embed_model_name)
                embeddings = model.get_embeddings(texts[:20])  # batch limit
                return [e.values for e in embeddings]

            result = await loop.run_in_executor(None, _embed)
            logger.info(f"Vertex AI embeddings: {len(result)} vectors")
            return result

        except Exception as e:
            logger.warning(f"Vertex AI embedding failed: {e}")
            return []


vertex_service = VertexAIService()
