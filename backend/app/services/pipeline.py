"""
LexGuard Pipeline — 3 API calls total (Extract → Batch Risk → Batch Deep).
"""
import logging
import time
from pathlib import Path

from app.core.config import settings
from app.models.schemas import (
    DocumentRecord, DocumentStatus, DocumentMetadata, PrivacyComplianceResult, MarketBenchmarkResult, RelationshipMappingResult,
)
from app.services.analysis_engine import AnalysisEngine
from app.services.database import db_service
from app.services.document_processor import DocumentProcessor
from app.services.progress_service import progress_service
from app.services.rag_service import RAGService

logger = logging.getLogger(__name__)
rag_service = RAGService()


class PipelineOrchestrator:
    def __init__(self):
        self.doc_processor = DocumentProcessor()
        self.analysis_engine = AnalysisEngine()

    async def _progress(self, doc_id: str, *, status, message: str, percent: int, step: str, detail: str = ""):
        await progress_service.emit(
            doc_id, status=status, message=message,
            percent=percent, step=step, detail=detail
        )

    async def run_pipeline(self, doc_record: DocumentRecord, filepath: str) -> DocumentRecord:
        start = time.time()
        doc_id = doc_record.id

        try:
            if not settings.llm_is_configured():
                raise ValueError(
                    "No LLM configured. Set GEMINI_API_KEY or OPENROUTER_API_KEY in backend/.env"
                )
            logger.info(f"[{doc_id}] provider={settings.resolved_llm_provider()} model={self.analysis_engine.model}")
            progress_service.clear(doc_id)

            # ── Step 1: Parse document ────────────────────────────────────────
            doc_record.status = DocumentStatus.PROCESSING
            await self._progress(doc_id, status=DocumentStatus.PROCESSING, message="Parsing document…", percent=5, step="parse")
            await db_service.save_document(doc_record)

            result = await self.doc_processor.process_file(filepath)
            doc_record.raw_text = result["raw_text"]
            doc_record.normalized_text = result["normalized_text"]
            doc_record.sections = result.get("sections", [])
            doc_record.metadata = DocumentMetadata(
                author=result["metadata"].get("author", ""),
                creation_date=result["metadata"].get("creation_date", ""),
                page_count=result["metadata"].get("page_count", 0),
                word_count=result.get("word_count", 0),
                file_type=doc_record.file_type,
                file_size_bytes=Path(filepath).stat().st_size,
            )

            if not doc_record.normalized_text.strip():
                return await self._fail(doc_record, "No text extracted from document.", start)

            await self._progress(doc_id, status=DocumentStatus.PROCESSING,
                                 message=f"Parsed {doc_record.metadata.word_count:,} words", percent=15, step="parse")

            # ── Step 2: RAG index (optional, non-blocking) ────────────────────
            if settings.RAG_ENABLED:
                await self._progress(doc_id, status=DocumentStatus.EXTRACTING,
                                     message="Building retrieval index…", percent=18, step="rag")
                chunks = self.doc_processor.chunk_text(doc_record.normalized_text,
                                                       settings.CHUNK_SIZE_TOKENS, settings.CHUNK_OVERLAP_TOKENS)
                try:
                    await rag_service.index_document(doc_id, chunks)
                except Exception as e:
                    logger.warning(f"RAG index failed (non-fatal): {e}")

            # ── CALL 1: Extract ALL clauses ───────────────────────────────────
            doc_record.status = DocumentStatus.EXTRACTING
            await db_service.save_document(doc_record)
            await self._progress(doc_id, status=DocumentStatus.EXTRACTING,
                                 message="Extracting clauses (API call 1/3)…", percent=25, step="extract")

            rag_ctx = ""
            if settings.RAG_ENABLED:
                try:
                    rag_ctx = await rag_service.retrieve(doc_id, doc_record.normalized_text[:500])
                except Exception:
                    pass

            clauses = await self.analysis_engine.extract_clauses(doc_record.normalized_text, rag_context=rag_ctx)

            # Deduplicate
            seen, unique = set(), []
            for c in clauses:
                key = c.text[:80].lower().strip()
                if key and key not in seen:
                    seen.add(key)
                    unique.append(c)
            clauses = unique

            if not clauses:
                return await self._fail(doc_record,
                    "AI returned no clauses. Check API quota or try a different document.", start)

            doc_record.extracted_clauses = clauses
            await self._progress(doc_id, status=DocumentStatus.EXTRACTING,
                                 message=f"Found {len(clauses)} clauses", percent=45, step="extract")

            # ── CALL 2: Batch risk classification ─────────────────────────────
            doc_record.status = DocumentStatus.ANALYZING
            await db_service.save_document(doc_record)
            await self._progress(doc_id, status=DocumentStatus.ANALYZING,
                                 message=f"Scoring {len(clauses)} clauses (API call 2/3)…", percent=55, step="analyze")

            risk_map = await self.analysis_engine.batch_classify_risks(clauses)
            risk_analyses = [risk_map.get(c.id, self.analysis_engine._default_risk(c.id)) for c in clauses]
            doc_record.risk_analyses = risk_analyses

            await self._progress(doc_id, status=DocumentStatus.ANALYZING,
                                 message="Risk scoring complete", percent=72, step="analyze")

            # ── CALL 3: Batch deep analysis for HIGH/CRITICAL only ────────────
            high_risk = [
                (c, risk_map[c.id]) for c in clauses
                if c.id in risk_map and risk_map[c.id].severity_score >= 6.0
            ][:8]

            doc_record.implications = []
            doc_record.ambiguities = []
            doc_record.negotiation_guidance = []
            doc_record.market_benchmarks = []
            doc_record.privacy_compliance = []
            doc_record.relationships = []

            if high_risk:
                await self._progress(doc_id, status=DocumentStatus.ANALYZING,
                                     message=f"Deep analysis: {len(high_risk)} high-risk clauses (API call 3/3)…",
                                     percent=80, step="deep")
                deep = await self.analysis_engine.batch_deep_analysis(high_risk)
                doc_record.implications       = deep.get("implications", [])
                doc_record.ambiguities        = deep.get("ambiguities", [])
                doc_record.negotiation_guidance = deep.get("negotiation", [])

                # Lightweight local stubs for market/privacy/relationships (no extra API calls)
                for clause, risk in high_risk:
                    doc_record.market_benchmarks.append(
                        MarketBenchmarkResult(clause_id=clause.id, market_standard="",
                                              is_standard=risk.severity_score < 6,
                                              deviation_severity=risk.severity_level,
                                              industry_context="", favorable_alternatives=[],
                                              risk_if_accepted=risk.severity_reasoning[:120])
                    )
                    doc_record.privacy_compliance.append(
                        PrivacyComplianceResult(clause_id=clause.id,
                                                gdpr_compliant=clause.type not in ("DATA_COLLECTION", "THIRD_PARTY_SHARING"),
                                                ccpa_compliant=clause.type not in ("DATA_COLLECTION", "THIRD_PARTY_SHARING"),
                                                violations=[], recommendations=[])
                    )
                    doc_record.relationships.append(
                        RelationshipMappingResult(clause_id=clause.id, related_clauses=[],
                                                  conflicts=[], dependencies=[], cascade_risks=[])
                    )

            # ── Step 5: Overall risk (local, 0 tokens) ────────────────────────
            await self._progress(doc_id, status=DocumentStatus.ANALYZING,
                                 message="Computing overall risk score…", percent=93, step="report")
            overall = self.analysis_engine.compute_overall_risk(risk_analyses)
            doc_record.overall_risk_score    = overall["overall_score"]
            doc_record.overall_severity      = overall["severity_level"]
            doc_record.signing_recommendation = overall["signing_recommendation"]
            doc_record.key_findings          = overall["key_findings"]

            doc_record.status = DocumentStatus.COMPLETED
            doc_record.processing_time_seconds = round(time.time() - start, 2)
            await db_service.save_document(doc_record)
            rag_service.clear_document(doc_id)

            n_calls = 2 + (1 if high_risk else 0)
            await progress_service.emit_complete(
                doc_id, status="completed",
                message=f"{overall['severity_level']} risk ({overall['overall_score']}/100) — {n_calls} API calls"
            )
            logger.info(f"[{doc_id}] Done in {doc_record.processing_time_seconds}s | "
                        f"{n_calls} API calls | {len(clauses)} clauses | score={overall['overall_score']}")
            return doc_record

        except Exception as e:
            msg = str(e)
            logger.error(f"[{doc_id}] Pipeline error: {msg}")
            await progress_service.emit_error(doc_id, msg)
            doc_record.status = DocumentStatus.FAILED
            doc_record.error_message = msg
            doc_record.processing_time_seconds = round(time.time() - start, 2)
            await db_service.save_document(doc_record)
            rag_service.clear_document(doc_id)
            return doc_record

    async def _fail(self, doc: DocumentRecord, msg: str, start: float) -> DocumentRecord:
        doc.status = DocumentStatus.FAILED
        doc.error_message = msg
        doc.processing_time_seconds = round(time.time() - start, 2)
        await progress_service.emit_error(doc.id, msg)
        await db_service.save_document(doc)
        rag_service.clear_document(doc.id)
        return doc
