<p align="center">
  <img src="https://img.shields.io/badge/LexGuard-AI%20Contract%20Intelligence-6366f1?style=for-the-badge&logo=scales&logoColor=white"/>
</p>

<h1 align="center">⚖️ LexGuard — AI Rights & Contract Intelligence System</h1>

<p align="center">
  <strong>Upload any contract → get a full risk report in 15–25 seconds → chat with your AI Lawyer</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white"/>
  <img src="https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white"/>
  <img src="https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=white"/>
  <img src="https://img.shields.io/badge/Google%20Cloud-Run-4285F4?logo=googlecloud&logoColor=white"/>
  <img src="https://img.shields.io/badge/Gemini-2.0%20Flash-orange?logo=google&logoColor=white"/>
  <img src="https://img.shields.io/badge/Tests-38%20passing-brightgreen?logo=pytest"/>
</p>

---

## 📋 Table of Contents

1. [What is LexGuard?](#-what-is-lexguard)
2. [Features](#-features)
3. [Architecture](#-architecture)
4. [Token-Optimized AI Pipeline](#-token-optimized-ai-pipeline)
5. [Google Cloud Integrations](#-google-cloud-integrations)
6. [Supported File Formats](#-supported-file-formats)
7. [Tech Stack](#-tech-stack)
8. [Project Structure](#-project-structure)
9. [Local Development Setup](#-local-development-setup)
10. [Environment Variables](#-environment-variables)
11. [Google Cloud Run Deployment](#-google-cloud-run-deployment)
12. [API Reference](#-api-reference)
13. [Security](#-security)
14. [Testing](#-testing)
15. [How We Built It](#-how-we-built-it)

---

## 🎯 What is LexGuard?

LexGuard is a **production-grade AI legal intelligence platform** that helps individuals and organisations understand contracts before signing them. Most people sign employment contracts, SaaS agreements, NDAs, and rental leases without understanding the legal implications — LexGuard changes that.

**Upload a contract → get an instant risk report → chat with an AI Lawyer → negotiate with confidence.**

---

## ✨ Features

### 🔍 Document Intelligence
- **Multi-format upload** — PDF, DOCX, XLSX, CSV, TXT, RTF, JPG, PNG
- **OCR support** — Google Cloud Vision API for scanned documents; Tesseract fallback
- **Structure-aware parsing** — Extracts headings, tables, headers/footers from DOCX; sheet names from XLSX
- **Magic-byte validation** — Verifies files are what they claim to be (prevents disguised malicious uploads)

### ⚖️ AI Legal Analysis
- **Clause extraction** — Identifies and classifies 30+ clause types (payment, non-compete, IP ownership, auto-renewal, arbitration, etc.)
- **Risk scoring** — Each clause scored 0–10 with severity: CRITICAL / HIGH / MEDIUM / LOW / NONE
- **Batch analysis** — All clauses scored in a single API call (3 calls total per document)
- **Deep analysis** — Implications, ambiguities, and negotiation guidance for HIGH/CRITICAL clauses
- **Signing recommendation** — Clear DO NOT SIGN / NEGOTIATE / REVIEW / ACCEPTABLE verdict

### 💬 AI Lawyer Chat
- **Context-aware conversation** — AI Lawyer knows all clauses, risk scores, findings, and your contract
- **Negotiation coaching** — Suggests alternative clause language, walk-away conditions, compromise positions
- **Win-win framing** — Recommendations benefit both parties for realistic negotiations

### 📊 Risk Dashboard
- **Visual risk breakdown** — Severity distribution, top risks, overall score gauge
- **Clause inspector** — Drill into every clause with full risk analysis
- **Export report** — Download a formatted `.txt` report with all findings

### 🔴 Real-Time Progress
- **Server-Sent Events (SSE)** — Live progress updates as analysis runs
- **Step-by-step feedback** — Parse → Index → Extract → Score → Deep Analyze → Complete

### 🔒 Security
- **File magic-byte validation** — Rejects files that don't match their claimed type
- **Filename sanitisation** — Strips path traversal (`../`), Windows paths, special characters
- **Rate limiting** — 30 uploads/10 min, 60 chats/min per IP
- **Document ID validation** — All endpoints reject non-alphanumeric or oversized IDs
- **Proper HTTP codes** — 400 (bad file), 413 (too large), 422 (wrong state), 429 (rate limited), 503 (no API key)

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        User Browser                              │
│                   React + TypeScript + Vite                      │
│  UploadZone → LiveProgress → RiskDashboard → ClauseInspector    │
│                       AI Lawyer Chat                             │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTPS / SSE
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                  FastAPI Backend (Cloud Run)                      │
│                                                                   │
│  POST /upload → BackgroundTask → PipelineOrchestrator            │
│  GET  /events → SSE stream (real-time progress)                  │
│  POST /chat   → AnalysisEngine.chat()                            │
│  GET  /formats → supported formats + GCP service status          │
└──────┬──────────────┬──────────────┬────────────────┬───────────┘
       │              │              │                │
       ▼              ▼              ▼                ▼
  ┌─────────┐  ┌──────────┐  ┌──────────┐   ┌──────────────┐
  │Firestore│  │   GCS    │  │ Vertex AI│   │ Cloud Vision │
  │  (docs) │  │ (files)  │  │ (Gemini) │   │    (OCR)     │
  └─────────┘  └──────────┘  └──────────┘   └──────────────┘
       │                              │
       │ fallback                     │ fallback
       ▼                              ▼
  ┌─────────┐                  ┌──────────────┐
  │ MongoDB │                  │  Gemini API  │
  │(in-mem) │                  │  OpenRouter  │
  └─────────┘                  └──────────────┘
```

---

## ⚡ Token-Optimized AI Pipeline

The biggest engineering challenge was making AI analysis fast and affordable. Our solution: **3 API calls total**, regardless of how many clauses a contract has.

### Before (60+ API calls)
```
Per chunk:      extract_clauses()    ×  N_chunks    = 4–8 calls
Per clause:     classify_risk()      × N_clauses    = 10–15 calls
Per HR clause:  analyze_implications × HR_clauses   = 6 calls each
Per HR clause:  detect_ambiguities   × HR_clauses   = 6 calls each
Per HR clause:  benchmark_market     × HR_clauses   = 6 calls each
...
TOTAL: 60–120 calls | ~150,000 tokens | 60–90 seconds
```

### After (3 API calls)

```
CALL 1 ─ Extract ALL clauses         (1 call, full contract text)
          ↓ compact prompt, 4096 token response
          Extracts: id, type, ref, text, key_terms, parties, ambiguities

CALL 2 ─ Batch-score ALL clause risks (1 call, all clauses in one JSON array)
          ↓ "id|TYPE|text" format, scored together
          Returns: severity, score, reason, likelihood, recommendation

CALL 3 ─ Batch deep analysis          (1 call, all HIGH/CRITICAL clauses)
          ↓ covers implications + ambiguities + negotiation together
          Returns: scenarios, ambiguity, negotiation per clause

LOCAL  ─ Overall score, market stubs, privacy stubs (0 tokens, instant)
```

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| API calls | 60–120 | **3** | **97% reduction** |
| Tokens/doc | ~150,000 | ~18,000 | **88% reduction** |
| Time | 60–90s | **15–25s** | **3× faster** |
| Cost/doc | ~$0.11 | **~$0.01** | **10× cheaper** |

### RAG (Retrieval-Augmented Generation)
- Contract text is chunked and indexed in memory on upload
- Relevant chunks retrieved for clause extraction context
- Skipped for small documents to save tokens

---

## ☁️ Google Cloud Integrations

| Service | Purpose | Fallback |
|---------|---------|---------|
| **Vertex AI (Gemini Flash)** | Primary LLM — no API key needed on Cloud Run (Workload Identity) | Direct Gemini API → OpenRouter |
| **Cloud Vision API** | OCR for scanned PDFs and images — highest accuracy | Tesseract (local) |
| **Cloud Storage (GCS)** | Stores uploaded contract files (survives container restarts) | Local `/tmp/uploads` |
| **Cloud Firestore** | Persistent document & analysis database | MongoDB → In-Memory |
| **Cloud Natural Language** | Contract language detection (multilingual support) | Default to `en` |
| **Cloud Run** | Fully managed container hosting (scales to 0) | — |

**On Cloud Run, zero credentials needed** — services use the Cloud Run service account via Workload Identity Federation.

---

## 📄 Supported File Formats

| Format | OCR | Tables | Structure | Notes |
|--------|-----|--------|-----------|-------|
| `.pdf` | ✅ Cloud Vision | ✅ | ✅ | Scanned pages auto-detected and OCR'd |
| `.docx` | — | ✅ | ✅ | Headings, tables, headers/footers |
| `.xlsx` / `.xls` | — | ✅ | — | Multi-sheet, all data extracted |
| `.csv` | — | ✅ | — | Header row detection |
| `.txt` | — | — | ✅ | Multi-encoding (UTF-8, Latin-1, CP1252) |
| `.rtf` | — | — | ✅ | RTF control words stripped |
| `.jpg` / `.jpeg` | ✅ Cloud Vision | — | — | Full document OCR |
| `.png` | ✅ Cloud Vision | — | — | Full document OCR |

Max file size: **50 MB**

---

## 🛠️ Tech Stack

### Backend
| Layer | Technology |
|-------|-----------|
| Framework | FastAPI 0.115 + Uvicorn |
| AI/LLM | Google Gemini 2.0 Flash (via Vertex AI or direct API) |
| Document parsing | pdfplumber, python-docx, openpyxl, Pillow, pytesseract |
| OCR | Google Cloud Vision API → Tesseract |
| Database | Google Cloud Firestore → MongoDB (motor) → In-Memory |
| File storage | Google Cloud Storage → Local filesystem |
| Real-time | Server-Sent Events (SSE) |
| Security | Magic-byte validation, rate limiting, filename sanitisation |
| Testing | pytest, httpx, pytest-asyncio |

### Frontend
| Layer | Technology |
|-------|-----------|
| Framework | React 18 + TypeScript + Vite |
| Styling | Vanilla CSS (glassmorphism, dark mode) |
| State | React hooks (useState, useCallback, useEffect) |
| Icons | Lucide React |
| Build | Vite 6 |

### Infrastructure
| Service | Technology |
|---------|-----------|
| Hosting | Google Cloud Run (fully managed) |
| Container | Docker (multi-stage builds) |
| CDN/Proxy | Nginx (frontend static serving) |
| CI/CD | `deploy.sh` one-command deployment |

---

## 📁 Project Structure

```
obligation_preventer/
├── backend/
│   ├── app/
│   │   ├── api/endpoints/
│   │   │   └── documents.py        # Upload, analyze, chat, list, formats endpoints
│   │   ├── core/
│   │   │   └── config.py           # All settings (GCP, LLM, upload, DB)
│   │   ├── data/
│   │   │   └── legal_knowledge.py  # 16-entry RAG knowledge base
│   │   ├── models/
│   │   │   └── schemas.py          # Pydantic models for all API contracts
│   │   ├── services/
│   │   │   ├── analysis_engine.py  # 3-call batch LLM engine (token-optimized)
│   │   │   ├── pipeline.py         # Orchestrates full analysis workflow
│   │   │   ├── document_processor.py # Multi-format parser (PDF/DOCX/XLSX/CSV/RTF/Image)
│   │   │   ├── database.py         # Firestore → MongoDB → Memory priority chain
│   │   │   ├── firestore_service.py # Google Cloud Firestore async client
│   │   │   ├── gcs_service.py      # Google Cloud Storage (upload/download/delete)
│   │   │   ├── vertex_service.py   # Vertex AI (Gemini enterprise, no API key on CR)
│   │   │   ├── vision_service.py   # Cloud Vision OCR + Tesseract fallback
│   │   │   ├── rag_service.py      # In-memory RAG for clause context
│   │   │   └── progress_service.py # SSE progress event emitter
│   │   └── utils/
│   │       └── security.py         # Magic bytes, sanitise, rate limiter, key validator
│   ├── tests/
│   │   └── test_backend.py         # 38 tests (security, config, endpoints, engine)
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── .env.example
│   └── .env
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── UploadZone.tsx       # Drag-drop upload (ARIA accessible)
│   │   │   ├── RiskDashboard.tsx    # Risk score visualization
│   │   │   ├── ClauseInspector.tsx  # Per-clause deep-dive UI
│   │   │   ├── LiveAnalysisProgress.tsx # SSE-powered progress bar
│   │   │   ├── DocumentCard.tsx    # Document list item
│   │   │   └── Sidebar.tsx         # Navigation sidebar
│   │   ├── utils/
│   │   │   └── reportExport.ts     # Client-side report generator (→ .txt download)
│   │   ├── api.ts                  # All backend API calls + TypeScript types
│   │   ├── App.tsx                 # Main app shell, routing, chat UI
│   │   └── index.css               # Global dark-mode design system
│   ├── Dockerfile
│   └── nginx.conf
│
├── sample_contracts/
│   └── risky_saas_agreement.txt    # Sample contract for testing
│
└── deploy.sh                       # One-command Google Cloud Run deployment
```

---

## 🚀 Local Development Setup

### Prerequisites
- Python 3.11+
- Node.js 18+
- MongoDB (optional — falls back to in-memory)
- A Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey)

### Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env — set GEMINI_API_KEY=your-key-here

# Run server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Backend runs at: `http://localhost:8000`  
API docs: `http://localhost:8000/docs`

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Run dev server
npm run dev
```

Frontend runs at: `http://localhost:5173`

### Run Tests

```bash
cd backend
source venv/bin/activate
python -m pytest tests/test_backend.py -v
# Expected: 38 passed
```

---

## 🔑 Environment Variables

Create `backend/.env` from `backend/.env.example`:

```env
# LLM Provider: auto | vertex | gemini | openrouter
# auto priority: Vertex AI (GCP) → Gemini → OpenRouter
LLM_PROVIDER=gemini

# ── Google Gemini (local dev) ──────────────────────────
GEMINI_API_KEY=your-key-from-aistudio.google.com
GEMINI_MODEL=gemini-2.0-flash

# ── OpenRouter (alternative) ───────────────────────────
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_MODEL=google/gemini-2.0-flash-001

# ── Google Cloud (production) ──────────────────────────
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_REGION=us-central1
GCS_BUCKET_NAME=your-project-uploads
FIRESTORE_COLLECTION=lexguard_documents

# ── Database ───────────────────────────────────────────
MONGODB_URL=mongodb://localhost:27017
MONGODB_DB_NAME=lexguard

# ── Upload ─────────────────────────────────────────────
MAX_FILE_SIZE_MB=50
UPLOAD_DIR=/tmp/uploads

# ── App ────────────────────────────────────────────────
PORT=8000
DEBUG=true
```

> **On Google Cloud Run**: set only `GOOGLE_CLOUD_PROJECT`. No API key needed — Vertex AI uses the service account automatically.

---

## ☁️ Google Cloud Run Deployment

### One-Command Deploy

```bash
# Clone and set up
git clone https://github.com/erantianantha/lexguard-ai.git
cd lexguard-ai

# Set your GCP project
export GOOGLE_CLOUD_PROJECT=your-project-id

# Deploy everything
chmod +x deploy.sh
./deploy.sh
```

The script automatically:
1. ✅ Enables all required GCP APIs
2. ✅ Creates a GCS bucket for file storage
3. ✅ Initialises Firestore (Native mode)
4. ✅ Builds & pushes both Docker images
5. ✅ Deploys backend Cloud Run service
6. ✅ Deploys frontend Cloud Run service
7. ✅ Wires CORS between services

### Manual Deployment Steps

See the full guide in [GCP_Deployment_Guide.md](./GCP_Deployment_Guide.md).

### Infrastructure Cost (Low Volume)

| Service | Free Tier | ~1000 docs/month |
|---------|-----------|-----------------|
| Cloud Run | 2M req free | ~$0 |
| Vertex AI (Gemini Flash) | — | ~$0.54 |
| Cloud Storage | 5 GB free | ~$0.02 |
| Firestore | 50K reads free | ~$0 |
| Cloud Vision | 1000 units free | ~$0 |

**Total: ~$0.60/month** for 1000 contract analyses.

---

## 🔌 API Reference

### Upload Document
```http
POST /api/v1/documents/upload
Content-Type: multipart/form-data

file: <contract file>
```

### Get Analysis
```http
GET /api/v1/documents/{id}/analysis
```

### Real-Time Progress (SSE)
```http
GET /api/v1/documents/{id}/events
Accept: text/event-stream
```

### Chat with AI Lawyer
```http
POST /api/v1/documents/{id}/chat
Content-Type: application/json

{
  "message": "How should I negotiate the non-compete clause?",
  "history": []
}
```

### List Documents
```http
GET /api/v1/documents/list
```

### Supported Formats + GCP Status
```http
GET /api/v1/documents/formats
```

### Settings
```http
GET  /api/v1/settings
POST /api/v1/settings
Content-Type: application/json
{"api_key": "AIza...", "provider": "gemini"}
```

---

## 🔒 Security

### File Security
- **Magic-byte validation** — `%PDF` for PDFs, `\x89PNG` for PNGs, `PK\x03\x04` for DOCX/XLSX
- **Filename sanitisation** — Strips `../`, `//`, Windows paths, control characters
- **Size limit** — 50 MB hard cap before any processing

### API Security
- **Rate limiting** — In-memory sliding window: 30 uploads/10 min, 60 chats/min per IP
- **Document ID validation** — Alphanumeric only, max 64 characters
- **Input sanitisation** — All path parameters validated before DB or filesystem access

### Deployment Security
- **No secrets in code** — All keys via environment variables
- **Cloud Run** — Fully managed, no SSH access, auto-scaled containers
- **Workload Identity** — No service account keys on Cloud Run (uses metadata server)
- **CORS** — Locked to frontend domain in production

---

## 🧪 Testing

```bash
cd backend
source venv/bin/activate
python -m pytest tests/test_backend.py -v
```

**38 tests across 10 test classes:**

| Class | Tests | What it covers |
|-------|-------|----------------|
| `TestSanitiseFilename` | 5 | Path traversal, special chars, length limits |
| `TestFilemagic` | 5 | Magic byte validation for all formats |
| `TestApiKeyFormat` | 3 | Empty, short, valid key format checks |
| `TestRateLimiter` | 4 | Allow, block, independent users, reset |
| `TestSettings` | 6 | Provider resolution, auto-mode, Vertex priority |
| `TestAnalysisEngine` | 5 | JSON parsing (direct, markdown, embedded, invalid), default risk |
| `TestHealthEndpoint` | 1 | `GET /health` returns 200 |
| `TestSettingsEndpoint` | 3 | GET settings, invalid provider, valid update |
| `TestUploadEndpoint` | 3 | Bad extension, empty file, missing API key |
| `TestDocumentEndpoints` | 3 | List, 404, invalid ID |

---

## 🏗️ How We Built It

### Problem
People sign contracts without understanding them. Complex legal language, buried clauses, and one-sided terms cause financial harm, restrict careers, and erode rights.

### Solution Design
1. **Multi-format ingest** — Any contract format should work
2. **AI clause extraction** — LLM identifies every meaningful clause
3. **Risk classification** — Each clause scored on financial, legal, operational, privacy risk
4. **Deep analysis** — For high-risk clauses: scenarios, ambiguities, negotiation paths
5. **Chat interface** — Ask the AI Lawyer anything about your specific contract

### Key Engineering Decisions

#### 1. Token Budget Architecture
The single biggest constraint is API cost and speed. We redesigned from per-clause calls to batch operations, reducing calls from 60+ to 3 and tokens from 150K to 18K per document.

#### 2. Fallback Chain Design
Every component degrades gracefully:
- LLM: `Vertex AI → Gemini → OpenRouter`
- Storage: `GCS → /tmp`
- Database: `Firestore → MongoDB → In-Memory`
- OCR: `Cloud Vision → Tesseract`

This means the app runs identically in local dev (no GCP) and production (full GCP stack).

#### 3. Real-Time UX
Documents take 15–25 seconds to analyze. Rather than a spinner, we use Server-Sent Events to push named progress steps to the frontend in real time. Users see exactly what's happening.

#### 4. Legal Knowledge Base (RAG)
16 curated legal knowledge entries covering employment, SaaS, privacy (GDPR/CCPA), IP ownership, arbitration, auto-renewal, non-compete, force majeure, and insurance. These ground the AI's reasoning in real legal standards rather than hallucinated norms.

#### 5. Security-First Upload
Files are checked at three layers: HTTP (extension allowlist), byte-level (magic signature), and content (minimum word count). A file that passes all three is safe to process.

---

## 📜 Clause Types Detected

`DEFINITIONAL` · `RIGHTS_GRANTED` · `OBLIGATIONS` · `RESTRICTIONS` · `PAYMENT_TERMS` · `FEE_STRUCTURES` · `PENALTIES` · `REFUND_CANCELLATION` · `IP_OWNERSHIP` · `LICENSE_GRANTS` · `NON_COMPETE` · `NON_SOLICITATION` · `CONFIDENTIALITY` · `IP_ASSIGNMENT` · `LIABILITY_LIMITATION` · `INDEMNIFICATION` · `WARRANTY_DISCLAIMER` · `DISPUTE_RESOLUTION` · `DATA_COLLECTION` · `DATA_USAGE` · `THIRD_PARTY_SHARING` · `DATA_RETENTION` · `TERMINATION` · `AUTO_RENEWAL` · `CANCELLATION_PENALTY` · `SURVIVAL_CLAUSES` · `GOVERNING_LAW` · `AMENDMENT` · `ASSIGNMENT` · `FORCE_MAJEURE` · `OTHER`

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Run tests: `python -m pytest tests/ -v`
4. Commit: `git commit -m "feat: your feature"`
5. Push: `git push origin feature/your-feature`
6. Open a Pull Request

---

## 📄 License

MIT License — see [LICENSE](./LICENSE) for details.

---

<p align="center">
  Built with ⚖️ for people who deserve to understand what they sign.
</p>
