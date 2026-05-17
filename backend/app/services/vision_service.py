"""
Google Cloud Vision & Document AI Service for LexGuard.
Used for:
  - OCR of scanned PDFs and image documents (JPG/PNG)
  - Enhanced text extraction from complex layouts
  - Falls back to Tesseract / pdfplumber when Vision API is unavailable.
"""
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class VisionService:
    """
    Wraps Google Cloud Vision API for document OCR.
    Requires GOOGLE_APPLICATION_CREDENTIALS or Workload Identity on Cloud Run.
    """

    def __init__(self):
        self._client = None
        self._initialized = False

    def _init(self):
        if self._initialized:
            return
        try:
            from google.cloud import vision
            self._client = vision.ImageAnnotatorClient()
            self._initialized = True
            logger.info("✅ Google Cloud Vision API client initialized")
        except Exception as e:
            logger.warning(f"Cloud Vision unavailable ({e}) — Tesseract OCR will be used as fallback")
            self._client = None
            self._initialized = True  # don't retry

    @property
    def is_available(self) -> bool:
        self._init()
        return self._client is not None

    async def ocr_image_file(self, filepath: str) -> str:
        """
        Run OCR on an image file (JPG/PNG) using Cloud Vision API.
        Falls back to Tesseract if Vision is unavailable.
        Returns extracted text.
        """
        self._init()

        if self._client is not None:
            try:
                from google.cloud import vision
                with open(filepath, "rb") as f:
                    content = f.read()
                image = vision.Image(content=content)
                response = self._client.document_text_detection(image=image)
                if response.error.message:
                    raise RuntimeError(f"Vision API error: {response.error.message}")
                text = response.full_text_annotation.text
                logger.info(f"Cloud Vision OCR: {len(text)} chars from {Path(filepath).name}")
                return text
            except Exception as e:
                logger.warning(f"Cloud Vision OCR failed ({e}), falling back to Tesseract")

        # Tesseract fallback
        return await self._tesseract_ocr(filepath)

    async def ocr_pdf_page_image(self, image_bytes: bytes) -> str:
        """
        Run OCR on raw image bytes (e.g., a rendered PDF page).
        """
        self._init()
        if self._client is not None:
            try:
                from google.cloud import vision
                image = vision.Image(content=image_bytes)
                response = self._client.document_text_detection(image=image)
                if response.error.message:
                    raise RuntimeError(response.error.message)
                return response.full_text_annotation.text
            except Exception as e:
                logger.warning(f"Cloud Vision page OCR failed ({e})")
        return ""

    async def _tesseract_ocr(self, filepath: str) -> str:
        """Tesseract-based OCR fallback."""
        try:
            import pytesseract
            from PIL import Image
            image = Image.open(filepath)
            text = pytesseract.image_to_string(image)
            logger.info(f"Tesseract OCR: {len(text)} chars from {Path(filepath).name}")
            return text
        except ImportError:
            raise RuntimeError(
                "Neither Cloud Vision nor Tesseract is available. "
                "Install: pip install pytesseract && brew install tesseract"
            )
        except Exception as e:
            raise RuntimeError(f"Tesseract OCR failed: {e}")

    async def detect_document_language(self, text: str) -> str:
        """
        Detect the language of contract text using Cloud Natural Language API.
        Returns a BCP-47 language code (e.g. 'en', 'fr', 'de').
        Falls back to 'en' if unavailable.
        """
        try:
            from google.cloud import language_v1
            client = language_v1.LanguageServiceClient()
            document = language_v1.Document(
                content=text[:1000],  # sample first 1000 chars
                type_=language_v1.Document.Type.PLAIN_TEXT,
            )
            response = client.analyze_sentiment(request={"document": document})
            lang = response.language
            logger.info(f"Detected contract language: {lang}")
            return lang or "en"
        except Exception as e:
            logger.debug(f"Language detection unavailable: {e}")
            return "en"


vision_service = VisionService()
