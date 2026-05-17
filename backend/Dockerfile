# ── Render/Cloud Run compatible Dockerfile ──────────────────────────────────
# Uses python:3.11-slim-bookworm (Debian 12) for stable package availability.
# OCR/PDF system packages are installed with --fix-missing so build
# never fails even if an optional package is temporarily unavailable.
FROM python:3.11-slim-bookworm

WORKDIR /app

# Configure apt for reliability (retries + no interactive prompts)
ENV DEBIAN_FRONTEND=noninteractive
RUN echo 'Acquire::Retries "5";' > /etc/apt/apt.conf.d/80retries && \
    echo 'APT::Get::Assume-Yes "true";' >> /etc/apt/apt.conf.d/80retries

# ── Core system packages (required) ─────────────────────────────────────────
RUN apt-get update --fix-missing && \
    apt-get install -y --no-install-recommends \
        curl \
        libffi-dev \
        shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

# ── Optional OCR / PDF packages (non-fatal if unavailable) ──────────────────
# Code falls back gracefully: PDF→pdfplumber, OCR→pytesseract→error message
RUN apt-get update --fix-missing && \
    apt-get install -y --no-install-recommends --fix-missing \
        tesseract-ocr \
        tesseract-ocr-eng \
        poppler-utils \
    || echo "⚠️  Optional OCR/PDF system packages unavailable — fallback mode active" && \
    rm -rf /var/lib/apt/lists/*

# ── Python dependencies ──────────────────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ── Application code ─────────────────────────────────────────────────────────
COPY app/ ./app/

# Upload directory
RUN mkdir -p /tmp/uploads

# Non-root user for security
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Render uses PORT env var (default 10000); Cloud Run uses 8080
EXPOSE ${PORT:-10000}

CMD exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port ${PORT:-10000} \
    --workers 1 \
    --timeout-keep-alive 75 \
    --log-level info
