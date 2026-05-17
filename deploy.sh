#!/usr/bin/env bash
# ╔══════════════════════════════════════════════════════════╗
# ║  LexGuard — One-Command Google Cloud Run Deploy         ║
# ║  Usage: chmod +x deploy.sh && ./deploy.sh               ║
# ╚══════════════════════════════════════════════════════════╝
set -euo pipefail

# ── Config (edit these) ───────────────────────────────────
PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-lexguard-prod}"
REGION="${GOOGLE_CLOUD_REGION:-us-central1}"
BACKEND_IMAGE="gcr.io/${PROJECT_ID}/lexguard-backend"
FRONTEND_IMAGE="gcr.io/${PROJECT_ID}/lexguard-frontend"
GCS_BUCKET="${GCS_BUCKET_NAME:-${PROJECT_ID}-uploads}"
FIRESTORE_COLLECTION="lexguard_documents"

# ── Colours ───────────────────────────────────────────────
GREEN="\033[0;32m"; YELLOW="\033[1;33m"; RED="\033[0;31m"; NC="\033[0m"
info()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
error() { echo -e "${RED}[✗]${NC} $1"; exit 1; }

# ── Pre-flight checks ─────────────────────────────────────
command -v gcloud  >/dev/null || error "gcloud CLI not installed — https://cloud.google.com/sdk/docs/install"
command -v docker  >/dev/null || error "Docker not installed — https://docs.docker.com/get-docker/"
[[ -z "$PROJECT_ID" ]] && error "Set GOOGLE_CLOUD_PROJECT env var"

info "Project: $PROJECT_ID | Region: $REGION"
gcloud config set project "$PROJECT_ID"

# ── Enable APIs ───────────────────────────────────────────
info "Enabling required Google Cloud APIs…"
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  containerregistry.googleapis.com \
  firestore.googleapis.com \
  storage.googleapis.com \
  vision.googleapis.com \
  aiplatform.googleapis.com \
  --quiet

# ── Auth Docker ───────────────────────────────────────────
gcloud auth configure-docker --quiet

# ── GCS Bucket ───────────────────────────────────────────
if ! gsutil ls "gs://${GCS_BUCKET}" &>/dev/null; then
  info "Creating GCS bucket: $GCS_BUCKET"
  gsutil mb -p "$PROJECT_ID" -l "$REGION" "gs://${GCS_BUCKET}"
  gsutil lifecycle set - "gs://${GCS_BUCKET}" <<EOF
{"rule":[{"action":{"type":"Delete"},"condition":{"age":30}}]}
EOF
else
  warn "Bucket gs://${GCS_BUCKET} already exists"
fi

# ── Firestore ─────────────────────────────────────────────
info "Initialising Firestore (Native mode)…"
gcloud firestore databases create --location="$REGION" --quiet 2>/dev/null || \
  warn "Firestore already initialised"

# ── Build & push backend ──────────────────────────────────
info "Building backend Docker image…"
docker build -t "$BACKEND_IMAGE:latest" ./backend
docker push "$BACKEND_IMAGE:latest"

# ── Deploy backend to Cloud Run ───────────────────────────
info "Deploying backend to Cloud Run…"
gcloud run deploy lexguard-backend \
  --image "$BACKEND_IMAGE:latest" \
  --region "$REGION" \
  --platform managed \
  --allow-unauthenticated \
  --memory 1Gi \
  --cpu 1 \
  --concurrency 80 \
  --timeout 300 \
  --min-instances 0 \
  --max-instances 10 \
  --set-env-vars "\
GOOGLE_CLOUD_PROJECT=${PROJECT_ID},\
GOOGLE_CLOUD_REGION=${REGION},\
GCS_BUCKET_NAME=${GCS_BUCKET},\
FIRESTORE_COLLECTION=${FIRESTORE_COLLECTION},\
LLM_PROVIDER=auto,\
VERTEX_MODEL=gemini-2.0-flash,\
PORT=8080,\
DEBUG=false" \
  --quiet

BACKEND_URL=$(gcloud run services describe lexguard-backend \
  --region="$REGION" --format="value(status.url)")
info "Backend URL: $BACKEND_URL"

# ── Build & push frontend ─────────────────────────────────
info "Building frontend Docker image…"
docker build \
  --build-arg VITE_API_URL="${BACKEND_URL}/api/v1" \
  -t "$FRONTEND_IMAGE:latest" \
  ./frontend
docker push "$FRONTEND_IMAGE:latest"

# ── Deploy frontend to Cloud Run ──────────────────────────
info "Deploying frontend to Cloud Run…"
gcloud run deploy lexguard-frontend \
  --image "$FRONTEND_IMAGE:latest" \
  --region "$REGION" \
  --platform managed \
  --allow-unauthenticated \
  --memory 256Mi \
  --cpu 1 \
  --concurrency 200 \
  --min-instances 0 \
  --max-instances 5 \
  --set-env-vars "VITE_API_URL=${BACKEND_URL}/api/v1" \
  --quiet

FRONTEND_URL=$(gcloud run services describe lexguard-frontend \
  --region="$REGION" --format="value(status.url)")

# ── CORS: allow frontend to call backend ──────────────────
info "Updating backend CORS to allow $FRONTEND_URL …"
gcloud run services update lexguard-backend \
  --region "$REGION" \
  --update-env-vars "CORS_ORIGINS=${FRONTEND_URL}" \
  --quiet

info "════════════════════════════════════════════════"
info "  Deployment complete!"
info "  Frontend : $FRONTEND_URL"
info "  Backend  : $BACKEND_URL"
info "  Health   : ${BACKEND_URL}/health"
info "════════════════════════════════════════════════"
echo ""
warn "If you want to add a Gemini API key (for non-Vertex fallback):"
echo "  gcloud run services update lexguard-backend --region $REGION \\"
echo "    --update-env-vars GEMINI_API_KEY=<your-key>"
