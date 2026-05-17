"""
Document Processing Service — Full multi-format support with Google Cloud Vision OCR.
Supported formats:
  • TXT  — plain text contracts
  • PDF  — pdfplumber (text) → Cloud Vision OCR (scanned) → PyPDF2 fallback
  • DOCX — python-docx (structure-aware)
  • XLSX — openpyxl (spreadsheet agreements)
  • JPG/JPEG/PNG — Cloud Vision OCR → Tesseract fallback
  • CSV  — tabular data contracts
  • RTF  — rich text format contracts

Format detection uses magic bytes, not just file extension.
"""
import csv
import hashlib
import io
import logging
import os
import re
from pathlib import Path
from typing import Optional

from app.core.config import settings
from app.utils.security import validate_file_magic

logger = logging.getLogger(__name__)


# ── MIME / Extension Maps ──────────────────────────────────────────────────────

SUPPORTED_FORMATS: dict[str, str] = {
    ".txt":  "plain_text",
    ".pdf":  "pdf",
    ".docx": "docx",
    ".xlsx": "xlsx",
    ".xls":  "xlsx",          # older Excel
    ".csv":  "csv",
    ".jpg":  "image",
    ".jpeg": "image",
    ".png":  "image",
    ".rtf":  "rtf",
}


class FormatVerificationResult:
    """Result of validating a file's format and content."""

    def __init__(self, *, ext: str, detected_format: str, magic_ok: bool,
                 readable: bool, word_count: int, error: Optional[str] = None):
        self.ext = ext
        self.detected_format = detected_format
        self.magic_ok = magic_ok
        self.readable = readable
        self.word_count = word_count
        self.error = error

    def to_dict(self) -> dict:
        return {
            "extension": self.ext,
            "detected_format": self.detected_format,
            "magic_bytes_valid": self.magic_ok,
            "readable": self.readable,
            "word_count": self.word_count,
            "error": self.error,
        }


class DocumentProcessor:
    """
    Multi-format document processor.
    Extracts text + metadata from contracts in any supported format.
    Uses Google Cloud Vision for image OCR when available.
    """

    def __init__(self):
        self.upload_dir = Path(settings.UPLOAD_DIR)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    # ── Public API ─────────────────────────────────────────────────────────────

    async def process_file(self, filepath: str) -> dict:
        """
        Process a file and return extracted text + metadata.
        Auto-detects format from extension.
        """
        ext = Path(filepath).suffix.lower()
        fmt = SUPPORTED_FORMATS.get(ext)

        if fmt is None:
            raise ValueError(
                f"Unsupported file format '{ext}'. "
                f"Supported: {', '.join(sorted(SUPPORTED_FORMATS.keys()))}"
            )

        logger.info(f"Processing {Path(filepath).name} as {fmt}")

        if fmt == "pdf":
            return await self._process_pdf(filepath)
        elif fmt == "docx":
            return await self._process_docx(filepath)
        elif fmt == "xlsx":
            return await self._process_xlsx(filepath)
        elif fmt == "csv":
            return await self._process_csv(filepath)
        elif fmt == "image":
            return await self._process_image(filepath)
        elif fmt == "rtf":
            return await self._process_rtf(filepath)
        elif fmt == "plain_text":
            return await self._process_txt(filepath)
        else:
            raise ValueError(f"Internal error: unmapped format '{fmt}'")

    async def verify_format(self, filepath: str) -> FormatVerificationResult:
        """
        Verify that a file is actually in the format its extension claims.
        Returns a detailed verification result.
        """
        ext = Path(filepath).suffix.lower()

        # Read header bytes for magic check
        try:
            with open(filepath, "rb") as f:
                header = f.read(16)
        except OSError as e:
            return FormatVerificationResult(
                ext=ext, detected_format="unknown",
                magic_ok=False, readable=False, word_count=0,
                error=str(e),
            )

        magic_ok = validate_file_magic(header, ext)

        try:
            result = await self.process_file(filepath)
            word_count = result.get("word_count", 0)
            readable = word_count > 0
            return FormatVerificationResult(
                ext=ext,
                detected_format=SUPPORTED_FORMATS.get(ext, "unknown"),
                magic_ok=magic_ok,
                readable=readable,
                word_count=word_count,
            )
        except Exception as e:
            return FormatVerificationResult(
                ext=ext,
                detected_format=SUPPORTED_FORMATS.get(ext, "unknown"),
                magic_ok=magic_ok,
                readable=False,
                word_count=0,
                error=str(e),
            )

    # ── Format Processors ──────────────────────────────────────────────────────

    async def _process_txt(self, filepath: str) -> dict:
        """Plain text: UTF-8 with multiple encoding fallbacks."""
        encodings = ["utf-8", "utf-8-sig", "latin-1", "cp1252", "iso-8859-1"]
        raw_text = ""
        used_encoding = "utf-8"

        for enc in encodings:
            try:
                with open(filepath, "r", encoding=enc, errors="strict") as f:
                    raw_text = f.read()
                used_encoding = enc
                break
            except (UnicodeDecodeError, UnicodeError):
                continue

        if not raw_text:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                raw_text = f.read()

        normalized = self._normalize_text(raw_text)
        logger.info(f"TXT: {len(normalized.split())} words ({used_encoding})")

        return {
            "raw_text": raw_text,
            "normalized_text": normalized,
            "metadata": {"page_count": 1, "encoding": used_encoding},
            "sections": self._detect_sections(normalized),
            "word_count": len(normalized.split()),
            "file_hash": self._compute_hash(filepath),
            "format": "txt",
        }

    async def _process_pdf(self, filepath: str) -> dict:
        """
        PDF processing pipeline:
        1. pdfplumber for native text PDFs (best quality)
        2. Cloud Vision OCR for scanned pages with no text
        3. PyPDF2 fallback
        """
        # Try pdfplumber first
        try:
            import pdfplumber
            text_parts = []
            metadata = {}
            page_count = 0
            scanned_pages = 0

            with pdfplumber.open(filepath) as pdf:
                page_count = len(pdf.pages)
                raw_meta = pdf.metadata or {}
                metadata = {
                    "page_count": page_count,
                    "author": raw_meta.get("Author", "") or "",
                    "creation_date": str(raw_meta.get("CreationDate", "") or ""),
                    "title": raw_meta.get("Title", "") or "",
                    "producer": raw_meta.get("Producer", "") or "",
                }

                for page_num, page in enumerate(pdf.pages):
                    page_text = page.extract_text() or ""

                    # If page has very little text, it may be scanned → try Vision OCR
                    if len(page_text.split()) < 10:
                        scanned_pages += 1
                        vision_text = await self._ocr_pdf_page(page)
                        if vision_text:
                            page_text = vision_text
                            logger.info(f"PDF p{page_num+1}: OCR extracted {len(vision_text.split())} words")

                    if page_text.strip():
                        text_parts.append(page_text)

                    # Extract tables
                    for table in (page.extract_tables() or []):
                        for row in table:
                            if row:
                                row_text = " | ".join(str(c or "") for c in row)
                                if row_text.strip():
                                    text_parts.append(row_text)

            if scanned_pages > 0:
                metadata["scanned_pages"] = scanned_pages
                metadata["ocr_used"] = True

            raw_text = "\n\n".join(text_parts)
            normalized = self._normalize_text(raw_text)
            logger.info(f"PDF: {page_count} pages, {len(normalized.split())} words")

            return {
                "raw_text": raw_text,
                "normalized_text": normalized,
                "metadata": metadata,
                "sections": self._detect_sections(normalized),
                "word_count": len(normalized.split()),
                "file_hash": self._compute_hash(filepath),
                "format": "pdf",
            }

        except ImportError:
            logger.warning("pdfplumber not installed — using PyPDF2")
            return await self._process_pdf_pypdf2(filepath)

    async def _ocr_pdf_page(self, page) -> str:
        """Render a PDF page to image and run Cloud Vision OCR."""
        try:
            # pdfplumber uses pdfminer underneath — render page to image
            img = page.to_image(resolution=150)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            image_bytes = buf.getvalue()

            from app.services.vision_service import vision_service
            return await vision_service.ocr_pdf_page_image(image_bytes)
        except Exception as e:
            logger.debug(f"PDF page OCR failed: {e}")
            return ""

    async def _process_pdf_pypdf2(self, filepath: str) -> dict:
        """PyPDF2 fallback for PDF processing."""
        from PyPDF2 import PdfReader

        reader = PdfReader(filepath)
        text_parts = []

        for page in reader.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)

        raw_text = "\n\n".join(text_parts)
        normalized = self._normalize_text(raw_text)
        meta = reader.metadata or {}

        return {
            "raw_text": raw_text,
            "normalized_text": normalized,
            "metadata": {
                "page_count": len(reader.pages),
                "author": str(meta.get("/Author", "") or ""),
                "creation_date": str(meta.get("/CreationDate", "") or ""),
            },
            "sections": self._detect_sections(normalized),
            "word_count": len(normalized.split()),
            "file_hash": self._compute_hash(filepath),
            "format": "pdf",
        }

    async def _process_docx(self, filepath: str) -> dict:
        """
        DOCX processing with structure preservation.
        Extracts headings, paragraphs, tables, headers/footers, and comments.
        """
        try:
            from docx import Document
            from docx.oxml.ns import qn
        except ImportError:
            raise RuntimeError("python-docx is not installed: pip install python-docx")

        doc = Document(filepath)
        text_parts = []
        sections_detected = []

        # Core properties
        props = doc.core_properties
        metadata = {
            "page_count": len(doc.sections),
            "author": props.author or "",
            "creation_date": str(props.created or ""),
            "title": props.title or "",
            "subject": props.subject or "",
            "last_modified_by": props.last_modified_by or "",
        }

        # Paragraphs (preserve heading structure)
        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue
            text_parts.append(text)
            style_name = (para.style.name or "") if para.style else ""
            if "Heading" in style_name:
                level = 1
                try:
                    level = int(style_name.split()[-1])
                except (ValueError, IndexError):
                    pass
                sections_detected.append({"title": text, "level": level, "line_number": len(text_parts)})

        # Tables
        for table in doc.tables:
            for row in table.rows:
                cells = [c.text.strip() for c in row.cells if c.text.strip()]
                if cells:
                    text_parts.append(" | ".join(cells))

        # Headers & Footers (often contain important contract info)
        for section in doc.sections:
            for header in [section.header, section.first_page_header]:
                if header:
                    for para in header.paragraphs:
                        if para.text.strip():
                            text_parts.append(f"[HEADER] {para.text.strip()}")

        raw_text = "\n\n".join(text_parts)
        normalized = self._normalize_text(raw_text)
        logger.info(f"DOCX: {len(normalized.split())} words, {len(sections_detected)} sections")

        return {
            "raw_text": raw_text,
            "normalized_text": normalized,
            "metadata": metadata,
            "sections": sections_detected if sections_detected else self._detect_sections(normalized),
            "word_count": len(normalized.split()),
            "file_hash": self._compute_hash(filepath),
            "format": "docx",
        }

    async def _process_xlsx(self, filepath: str) -> dict:
        """
        XLSX/XLS processing.
        Handles spreadsheet-format contracts (pricing tables, SLAs, etc.)
        """
        try:
            from openpyxl import load_workbook
        except ImportError:
            raise RuntimeError("openpyxl is not installed: pip install openpyxl")

        text_parts = []
        sheet_names = []

        try:
            wb = load_workbook(filepath, read_only=True, data_only=True)
        except Exception as e:
            raise RuntimeError(f"Cannot open XLSX file: {e}")

        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            sheet_names.append(sheet_name)
            text_parts.append(f"\n=== Sheet: {sheet_name} ===")

            for row in ws.iter_rows(values_only=True):
                non_empty = [str(cell) for cell in row if cell is not None and str(cell).strip()]
                if non_empty:
                    text_parts.append(" | ".join(non_empty))

        raw_text = "\n".join(text_parts)
        normalized = self._normalize_text(raw_text)
        logger.info(f"XLSX: {len(sheet_names)} sheets, {len(normalized.split())} words")

        return {
            "raw_text": raw_text,
            "normalized_text": normalized,
            "metadata": {
                "page_count": len(sheet_names),
                "sheets": sheet_names,
            },
            "sections": [],
            "word_count": len(normalized.split()),
            "file_hash": self._compute_hash(filepath),
            "format": "xlsx",
        }

    async def _process_csv(self, filepath: str) -> dict:
        """CSV processing — handles tabular agreements."""
        text_parts = []
        row_count = 0

        encodings = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]
        rows = []

        for enc in encodings:
            try:
                with open(filepath, newline="", encoding=enc) as f:
                    reader = csv.reader(f)
                    rows = list(reader)
                break
            except (UnicodeDecodeError, csv.Error):
                continue

        if rows:
            # Use first row as headers if it looks like headers
            header = rows[0]
            text_parts.append("Columns: " + " | ".join(str(h) for h in header))
            for row in rows[1:]:
                if any(str(c).strip() for c in row):
                    text_parts.append(" | ".join(str(c) for c in row))
                    row_count += 1

        raw_text = "\n".join(text_parts)
        normalized = self._normalize_text(raw_text)
        logger.info(f"CSV: {row_count} data rows, {len(normalized.split())} words")

        return {
            "raw_text": raw_text,
            "normalized_text": normalized,
            "metadata": {"page_count": 1, "row_count": row_count},
            "sections": [],
            "word_count": len(normalized.split()),
            "file_hash": self._compute_hash(filepath),
            "format": "csv",
        }

    async def _process_image(self, filepath: str) -> dict:
        """
        Image OCR: JPG/JPEG/PNG.
        Uses Cloud Vision API first, Tesseract as fallback.
        """
        from app.services.vision_service import vision_service

        # Validate it's a real image
        try:
            from PIL import Image as PILImage
            with PILImage.open(filepath) as img:
                width, height = img.size
                img_format = img.format
        except Exception as e:
            raise ValueError(f"Cannot open image file: {e}")

        raw_text = await vision_service.ocr_image_file(filepath)
        if not raw_text.strip():
            raise ValueError(
                "No text could be extracted from the image. "
                "Ensure the image contains readable contract text."
            )

        normalized = self._normalize_text(raw_text)
        ocr_method = "Cloud Vision" if vision_service.is_available else "Tesseract"
        logger.info(f"Image OCR ({ocr_method}): {width}×{height} px, {len(normalized.split())} words")

        return {
            "raw_text": raw_text,
            "normalized_text": normalized,
            "metadata": {
                "page_count": 1,
                "image_width": width,
                "image_height": height,
                "image_format": img_format or "unknown",
                "ocr_method": ocr_method,
            },
            "sections": self._detect_sections(normalized),
            "word_count": len(normalized.split()),
            "file_hash": self._compute_hash(filepath),
            "format": "image",
        }

    async def _process_rtf(self, filepath: str) -> dict:
        """RTF processing — strips RTF markup and extracts plain text."""
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                rtf_content = f.read()
        except OSError as e:
            raise RuntimeError(f"Cannot read RTF file: {e}")

        # Strip RTF control words and groups
        text = rtf_content
        text = re.sub(r"\\([a-z]+)(-?\d+)?[ ]?", " ", text)  # control words
        text = re.sub(r"\{|\}", "", text)                      # braces
        text = re.sub(r"\\[^a-z]", "", text)                  # control symbols
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text).strip()

        normalized = self._normalize_text(text)
        logger.info(f"RTF: {len(normalized.split())} words")

        return {
            "raw_text": text,
            "normalized_text": normalized,
            "metadata": {"page_count": 1},
            "sections": self._detect_sections(normalized),
            "word_count": len(normalized.split()),
            "file_hash": self._compute_hash(filepath),
            "format": "rtf",
        }

    # ── Text Processing ────────────────────────────────────────────────────────

    def _normalize_text(self, text: str) -> str:
        """Normalize extracted text for LLM analysis."""
        if not text:
            return ""

        # Unicode normalization
        text = text.replace("\u2018", "'").replace("\u2019", "'")
        text = text.replace("\u201c", '"').replace("\u201d", '"')
        text = text.replace("\u2013", "-").replace("\u2014", "-")
        text = text.replace("\u2026", "...").replace("\xa0", " ")
        text = text.replace("\u00a9", "(c)").replace("\u00ae", "(R)")

        # Remove page number patterns
        text = re.sub(r"Page \d+ of \d+", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\f", "\n", text)  # form feeds

        # Normalize whitespace
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)

        # Clean lines
        lines = [ln.strip() for ln in text.split("\n")]
        return "\n".join(lines).strip()

    def _detect_sections(self, text: str) -> list[dict]:
        """Detect contract section headers from text."""
        sections = []
        patterns = [
            r"^(?:SECTION|ARTICLE|PART|SCHEDULE|EXHIBIT|ANNEX)\s+[\dIVX]+[\.\:]?\s*(.+)",
            r"^(\d+\.)\s+([A-Z][A-Za-z\s]{3,})",
            r"^([A-Z][A-Z\s]{4,})\s*$",
            r"^(\d+\.\d+)\s+(.+)",
        ]
        lines = text.split("\n")
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped or len(stripped) > 120:
                continue
            for pattern in patterns:
                if re.match(pattern, stripped):
                    sections.append({
                        "title": stripped,
                        "line_number": i,
                        "level": 1 if any(k in stripped.upper() for k in ("SECTION", "ARTICLE", "PART")) else 2,
                    })
                    break
        return sections

    def chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 50) -> list[dict]:
        """Split text into overlapping chunks for LLM processing."""
        words = text.split()
        if len(words) <= chunk_size:
            return [{"chunk_id": 0, "text": text, "word_count": len(words)}]

        chunks = []
        i = 0
        chunk_id = 0
        while i < len(words):
            end = min(i + chunk_size, len(words))
            chunk_text = " ".join(words[i:end])
            chunks.append({
                "chunk_id": chunk_id,
                "text": chunk_text,
                "word_count": end - i,
                "start_word": i,
                "end_word": end,
            })
            i += chunk_size - overlap
            chunk_id += 1
        return chunks

    def _compute_hash(self, filepath: str) -> str:
        """SHA-256 hash for deduplication."""
        sha = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha.update(chunk)
        return sha.hexdigest()
