"""
Document API Endpoints — Upload, analyze, list, retrieve, chat.
Security: rate limiting, file magic validation, filename sanitisation.
"""
import json
import os
import uuid
import logging
from pathlib import Path
from datetime import datetime

from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Request
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.models.schemas import (
    DocumentRecord,
    DocumentUploadResponse,
    DocumentStatus,
    DocumentListItem,
    AnalysisResponse,
    ChatRequest,
    ChatResponse,
)
from app.services.database import db_service
from app.services.pipeline import PipelineOrchestrator
from app.services.progress_service import progress_service
from app.services.gcs_service import gcs_service
from app.utils.security import (
    sanitise_filename,
    validate_file_magic,
    upload_rate_limiter,
    chat_rate_limiter,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documents", tags=["Documents"])

pipeline = PipelineOrchestrator()


def _client_ip(request: Request) -> str:
    """Best-effort client IP extraction (supports X-Forwarded-For from Cloud Run)."""
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    """Upload a document for analysis. Processing runs in the background."""

    # ── Rate limit ────────────────────────────────────────────────────────────
    ip = _client_ip(request)
    if not upload_rate_limiter.is_allowed(ip):
        raise HTTPException(
            status_code=429,
            detail="Too many upload requests. Please wait before uploading again.",
        )

    # ── Validate extension ────────────────────────────────────────────────────
    original_name = file.filename or "upload"
    safe_name = sanitise_filename(original_name)
    ext = Path(safe_name).suffix.lower()

    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(settings.ALLOWED_EXTENSIONS)}",
        )

    # ── Read content ──────────────────────────────────────────────────────────
    content = await file.read()

    # ── File size check ───────────────────────────────────────────────────────
    size_mb = len(content) / (1024 * 1024)
    if size_mb > settings.MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({size_mb:.1f} MB). Maximum allowed: {settings.MAX_FILE_SIZE_MB} MB.",
        )

    if len(content) < 10:
        raise HTTPException(status_code=400, detail="File appears to be empty.")

    # ── Magic-byte validation ─────────────────────────────────────────────────
    if not validate_file_magic(content, ext):
        raise HTTPException(
            status_code=400,
            detail=f"File content does not match declared type '{ext}'. Upload rejected for security.",
        )

    # ── Check LLM is configured ───────────────────────────────────────────────
    if not settings.llm_is_configured():
        raise HTTPException(
            status_code=503,
            detail=(
                "No AI provider configured. "
                "Please go to Settings and enter your Gemini or OpenRouter API key first."
            ),
        )

    # ── Save to disk ──────────────────────────────────────────────────────────
    doc_id = uuid.uuid4().hex
    stored_filename = f"{doc_id}{ext}"
    filepath = os.path.join(settings.UPLOAD_DIR, stored_filename)
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    with open(filepath, "wb") as f:
        f.write(content)

    # ── Upload to GCS if configured ───────────────────────────────────────────
    file_ref = filepath  # local path by default
    if gcs_service.is_gcs_enabled:
        file_ref = await gcs_service.upload_file(filepath, doc_id, stored_filename)
        logger.info(f"File stored in GCS: {file_ref}")

    # ── Create DB record ──────────────────────────────────────────────────────
    doc_record = DocumentRecord(
        id=doc_id,
        filename=stored_filename,
        original_filename=safe_name,
        file_type=ext,
        status=DocumentStatus.UPLOADING,
    )
    await db_service.save_document(doc_record)

    await progress_service.emit(
        doc_id,
        status=DocumentStatus.PROCESSING.value,
        message="Upload complete — starting analysis…",
        percent=3,
        step="parse",
    )

    background_tasks.add_task(_run_pipeline_bg, doc_record, filepath)

    return DocumentUploadResponse(
        document_id=doc_id,
        filename=safe_name,
        status=DocumentStatus.PROCESSING,
        message="Document uploaded successfully. Analysis is running in the background.",
    )


async def _run_pipeline_bg(doc_record: DocumentRecord, filepath: str):
    """Background task to run the full analysis pipeline."""
    try:
        await pipeline.run_pipeline(doc_record, filepath)
    except Exception as e:
        logger.error(f"Background pipeline failed for {doc_record.id}: {e}", exc_info=True)
        doc_record.status = DocumentStatus.FAILED
        doc_record.error_message = str(e)
        await db_service.save_document(doc_record)


@router.get("/list", response_model=list[DocumentListItem])
async def list_documents(limit: int = 50, skip: int = 0):
    """List all uploaded documents with basic metadata."""
    if limit > 200:
        limit = 200
    docs = await db_service.list_documents(limit=limit, skip=skip)
    items = []
    for doc in docs:
        upload_date = doc.get("upload_date", "")
        if isinstance(upload_date, str):
            try:
                upload_date = datetime.fromisoformat(upload_date.replace("Z", "+00:00"))
            except ValueError:
                upload_date = datetime.utcnow()

        items.append(DocumentListItem(
            id=doc["id"],
            filename=doc.get("original_filename", doc.get("filename", "")),
            upload_date=upload_date,
            file_type=doc.get("file_type", ""),
            status=DocumentStatus(doc.get("status", "uploading")),
            overall_risk_score=doc.get("overall_risk_score", 0),
            overall_severity=doc.get("overall_severity", "LOW"),
            clause_count=len(doc.get("extracted_clauses", [])),
            page_count=doc.get("metadata", {}).get("page_count", 0) if isinstance(doc.get("metadata"), dict) else 0,
        ))
    return items


@router.get("/formats")
async def list_supported_formats():
    """
    List all supported file formats and their processing capabilities.
    Also reports which Google Cloud services are active.
    """
    from app.services.vision_service import vision_service
    from app.services.document_processor import SUPPORTED_FORMATS

    format_details = {
        ".txt":  {"name": "Plain Text",         "ocr": False, "tables": False, "structure": True},
        ".pdf":  {"name": "PDF Document",        "ocr": True,  "tables": True,  "structure": True},
        ".docx": {"name": "Word Document",       "ocr": False, "tables": True,  "structure": True},
        ".xlsx": {"name": "Excel Spreadsheet",   "ocr": False, "tables": True,  "structure": False},
        ".xls":  {"name": "Excel (Legacy)",      "ocr": False, "tables": True,  "structure": False},
        ".csv":  {"name": "CSV Spreadsheet",     "ocr": False, "tables": True,  "structure": False},
        ".jpg":  {"name": "JPEG Image",          "ocr": True,  "tables": False, "structure": False},
        ".jpeg": {"name": "JPEG Image",          "ocr": True,  "tables": False, "structure": False},
        ".png":  {"name": "PNG Image",           "ocr": True,  "tables": False, "structure": False},
        ".rtf":  {"name": "Rich Text Format",    "ocr": False, "tables": False, "structure": True},
    }

    formats = []
    for ext in settings.ALLOWED_EXTENSIONS:
        info = format_details.get(ext, {"name": ext, "ocr": False, "tables": False, "structure": False})
        formats.append({
            "extension": ext,
            "name": info["name"],
            "supported": True,
            "ocr_capable": info["ocr"],
            "table_extraction": info["tables"],
            "structure_aware": info["structure"],
            "max_size_mb": settings.MAX_FILE_SIZE_MB,
        })

    return {
        "supported_formats": formats,
        "total_supported": len(formats),
        "google_services": {
            "cloud_vision_ocr": vision_service.is_available,
            "cloud_storage": gcs_service.is_gcs_enabled,
            "llm_provider": settings.resolved_llm_provider() or "not configured",
            "llm_configured": settings.llm_is_configured(),
            "vertex_project": settings.GOOGLE_CLOUD_PROJECT or None,
        },
    }


@router.get("/{document_id}/events")
async def stream_document_events(document_id: str):
    """Server-Sent Events stream for real-time analysis progress."""
    if not document_id.isalnum() or len(document_id) > 64:
        raise HTTPException(status_code=400, detail="Invalid document ID.")

    doc = await db_service.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    async def event_generator():
        async for event in progress_service.subscribe(document_id):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{document_id}/status")
async def get_document_status(document_id: str):
    """Get the current processing status of a document."""
    if not document_id.isalnum() or len(document_id) > 64:
        raise HTTPException(status_code=400, detail="Invalid document ID.")

    doc = await db_service.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    latest = progress_service.get_latest(document_id) or {}
    return {
        "document_id": document_id,
        "status": doc.get("status", "unknown"),
        "error_message": doc.get("error_message"),
        "overall_risk_score": doc.get("overall_risk_score", 0),
        "overall_severity": doc.get("overall_severity", ""),
        "progress_percent": latest.get("percent", 0),
        "progress_message": latest.get("message", ""),
        "progress_step": latest.get("step", ""),
    }


@router.get("/{document_id}/analysis", response_model=AnalysisResponse)
async def get_analysis(document_id: str):
    """Get the full analysis results for a document."""
    if not document_id.isalnum() or len(document_id) > 64:
        raise HTTPException(status_code=400, detail="Invalid document ID.")

    doc = await db_service.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    status = doc.get("status", "")
    if status != DocumentStatus.COMPLETED.value:
        try:
            doc_status = DocumentStatus(status)
        except ValueError:
            doc_status = DocumentStatus.PROCESSING
        return AnalysisResponse(
            document_id=document_id,
            filename=doc.get("original_filename", doc.get("filename", "")),
            status=doc_status,
        )

    try:
        return pipeline.build_analysis_response(doc)
    except Exception as e:
        logger.error(f"Failed to build analysis response for {document_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to load analysis results.")


@router.post("/{document_id}/chat", response_model=ChatResponse)
async def chat_with_lawyer(document_id: str, request: ChatRequest, http_request: Request):
    """
    AI Lawyer chat endpoint.
    Aware of all extracted clauses, risks, ambiguities, and negotiation guidance.
    Uses the configured LLM provider from Settings.
    """
    # ── Input validation ──────────────────────────────────────────────────────
    if not document_id.isalnum() or len(document_id) > 64:
        raise HTTPException(status_code=400, detail="Invalid document ID.")

    ip = _client_ip(http_request)
    if not chat_rate_limiter.is_allowed(ip):
        raise HTTPException(status_code=429, detail="Too many chat requests. Please slow down.")

    if not request.messages:
        raise HTTPException(status_code=400, detail="No messages provided.")

    last_msg = request.messages[-1].content.strip()
    if not last_msg:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")
    if len(last_msg) > 2000:
        raise HTTPException(status_code=400, detail="Message too long. Maximum 2000 characters.")

    # ── Load document ─────────────────────────────────────────────────────────
    doc = await db_service.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    if doc.get("status") != DocumentStatus.COMPLETED.value:
        raise HTTPException(
            status_code=422,
            detail="Document analysis is not complete yet. Please wait before chatting.",
        )

    # ── Build rich context from ALL analysis data ─────────────────────────────
    engine = pipeline.analysis_engine

    context_parts: list[str] = []

    # Contract metadata
    meta = doc.get("metadata", {})
    context_parts.append(
        f"CONTRACT: {doc.get('original_filename', 'Unknown')}\n"
        f"Overall Risk: {doc.get('overall_severity', 'UNKNOWN')} ({doc.get('overall_risk_score', 0):.0f}/100)\n"
        f"Recommendation: {doc.get('signing_recommendation', '')}"
    )

    # Key findings
    key_findings = doc.get("key_findings", [])
    if key_findings:
        context_parts.append("KEY FINDINGS:\n" + "\n".join(f"• {f}" for f in key_findings))

    # High-risk clauses (top 12)
    clauses = doc.get("extracted_clauses", [])
    risks = doc.get("risk_analyses", [])
    risk_map = {r.get("clause_id"): r for r in risks}

    sorted_clauses = sorted(
        clauses,
        key=lambda c: risk_map.get(c.get("id", ""), {}).get("severity_score", 0),
        reverse=True,
    )

    clause_ctx = []
    for clause in sorted_clauses[:12]:
        cid = clause.get("id", "")
        risk = risk_map.get(cid, {})
        severity = risk.get("severity_level", "UNKNOWN")
        score = risk.get("severity_score", 0)
        reasoning = risk.get("severity_reasoning", "")
        recs = risk.get("recommendations", [])
        rec_text = "; ".join(r.get("action", "") for r in recs[:2])
        clause_ctx.append(
            f"[{clause.get('section_reference', cid)}] {clause.get('type', 'OTHER').replace('_', ' ')} "
            f"— {severity} risk ({score:.1f}/10)\n"
            f"Text: {clause.get('text', '')[:300]}\n"
            f"Risk: {reasoning[:200]}\n"
            f"Recommendation: {rec_text}"
        )
    if clause_ctx:
        context_parts.append("CLAUSE DETAILS:\n" + "\n\n".join(clause_ctx))

    # Ambiguities
    ambiguities = doc.get("ambiguities", [])
    amb_items = []
    for amb in ambiguities[:5]:
        for a in amb.get("ambiguities", [])[:2]:
            amb_items.append(f"• Term '{a.get('term', '')}': {a.get('issue', '')}")
    if amb_items:
        context_parts.append("AMBIGUOUS LANGUAGE:\n" + "\n".join(amb_items))

    # Negotiation guidance
    neg_guides = doc.get("negotiation_guidance", [])
    neg_items = []
    for ng in neg_guides[:5]:
        points = ng.get("leverage_points", [])
        redline = ng.get("suggested_redline", "")
        if points or redline:
            neg_items.append(f"• Leverage: {'; '.join(points[:2])}")
            if redline:
                neg_items.append(f"  Redline: {redline[:150]}")
    if neg_items:
        context_parts.append("NEGOTIATION GUIDANCE:\n" + "\n".join(neg_items))

    full_context = "\n\n---\n\n".join(context_parts)

    system_prompt = (
        "You are an expert AI lawyer and contract negotiator specialising in commercial, "
        "employment, SaaS, privacy, and intellectual property law. "
        "You have been given a complete analysis of a legal contract including extracted clauses, "
        "risk scores, ambiguities, and negotiation guidance. "
        "Your role is to help the user understand the contract, suggest how to negotiate specific "
        "clauses with the counterparty, propose alternative language that is fair to BOTH parties, "
        "and identify the most important issues to address before signing. "
        "Be specific, practical, and cite the clause sections when relevant. "
        "Do NOT give legally binding advice — recommend consulting a solicitor for complex matters. "
        "Return ONLY valid JSON in this exact format: "
        '{"response": "your detailed, structured advice here"}'
    )

    # Build chat history (keep last 10 turns for context window)
    history_block = ""
    for msg in request.messages[-11:-1]:
        role_label = "User" if msg.role == "user" else "AI Lawyer"
        history_block += f"{role_label}: {msg.content}\n"

    user_prompt = (
        f"CONTRACT ANALYSIS CONTEXT:\n{full_context}\n\n"
        f"{'CONVERSATION HISTORY:' + chr(10) + history_block if history_block else ''}"
        f"User question: {last_msg}\n\n"
        "Return JSON:"
    )

    try:
        response_text = await engine._call_llm(system_prompt, user_prompt, max_tokens=2000)
        result = engine._parse_json_response(response_text)
        answer = result.get("response", "")
        if not answer:
            # Fallback: use raw text if JSON parsing fails
            answer = response_text.strip().strip('"')
        return ChatResponse(response=answer)
    except ValueError as e:
        # LLM not configured
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"Chat failed for {document_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Chat request failed. Please try again.")


@router.delete("/{document_id}")
async def delete_document(document_id: str):
    """Delete a document and its analysis."""
    if not document_id.isalnum() or len(document_id) > 64:
        raise HTTPException(status_code=400, detail="Invalid document ID.")

    doc = await db_service.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    filepath = os.path.join(settings.UPLOAD_DIR, doc.get("filename", ""))
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
        except OSError as e:
            logger.warning(f"Could not delete file {filepath}: {e}")

    await db_service.delete_document(document_id)
    return {"message": "Document deleted successfully.", "document_id": document_id}
