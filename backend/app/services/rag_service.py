"""
RAG service — indexes document chunks and retrieves relevant contract + legal context.
"""
from __future__ import annotations

import logging
import math
import re
from typing import Any

import httpx

from app.core.config import settings
from app.data.legal_knowledge import LEGAL_KNOWLEDGE

logger = logging.getLogger(__name__)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _keyword_score(query: str, text: str) -> float:
    q_tokens = set(re.findall(r"[a-z0-9]+", query.lower()))
    if not q_tokens:
        return 0.0
    t_tokens = set(re.findall(r"[a-z0-9]+", text.lower()))
    return len(q_tokens & t_tokens) / len(q_tokens)


class RAGService:
    """Per-document vector index + legal knowledge retrieval."""

    def __init__(self):
        self._doc_chunks: dict[str, list[dict[str, Any]]] = {}
        self._kb_entries = LEGAL_KNOWLEDGE
        self._kb_vectors: list[list[float]] | None = None

    async def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        if settings.resolved_llm_provider() == "openrouter" and settings.OPENROUTER_API_KEY:
            url = f"{settings.OPENROUTER_BASE_URL.rstrip('/')}/embeddings"
            headers = {
                "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            }
            payload = {"model": settings.OPENROUTER_EMBEDDING_MODEL, "input": texts}
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code < 400:
                    data = resp.json()
                    items = sorted(data.get("data", []), key=lambda x: x.get("index", 0))
                    return [item["embedding"] for item in items]
                logger.warning(f"Embedding API returned {resp.status_code}, using keyword fallback")
            except Exception as e:
                logger.warning(f"Embedding request failed: {e}, using keyword fallback")

        # Keyword fallback: pseudo-vectors from token hashes (deterministic, lightweight)
        vectors = []
        for text in texts:
            tokens = re.findall(r"[a-z0-9]+", text.lower())[:64]
            vec = [0.0] * 32
            for tok in tokens:
                vec[hash(tok) % 32] += 1.0
            vectors.append(vec)
        return vectors

    async def index_document(self, document_id: str, chunks: list[dict[str, Any]]) -> int:
        """Index document text chunks for retrieval."""
        texts = [c.get("text", "") for c in chunks if c.get("text", "").strip()]
        if not texts:
            self._doc_chunks[document_id] = []
            return 0

        vectors = await self._embed_batch(texts)
        indexed = []
        for chunk, vector in zip(chunks, vectors):
            if not chunk.get("text", "").strip():
                continue
            indexed.append({
                "chunk_id": chunk.get("chunk_id", 0),
                "text": chunk["text"],
                "vector": vector,
            })
        self._doc_chunks[document_id] = indexed
        return len(indexed)

    async def _ensure_kb_vectors(self) -> None:
        if self._kb_vectors is not None:
            return
        texts = [e["text"] for e in self._kb_entries]
        self._kb_vectors = await self._embed_batch(texts)

    async def retrieve(
        self,
        document_id: str,
        query: str,
        *,
        doc_top_k: int = 3,
        legal_top_k: int = 2,
    ) -> str:
        """Build a context block from document chunks + legal knowledge."""
        parts: list[str] = []
        q_vec = (await self._embed_batch([query]))[0]

        doc_chunks = self._doc_chunks.get(document_id, [])
        if doc_chunks:
            scored = [
                (_cosine_similarity(q_vec, c["vector"]), c["text"])
                for c in doc_chunks
            ]
            scored.sort(key=lambda x: x[0], reverse=True)
            doc_hits = [t for s, t in scored[:doc_top_k] if s > 0.05]
            if doc_hits:
                parts.append("RELEVANT CONTRACT EXCERPTS:\n" + "\n---\n".join(doc_hits))

        await self._ensure_kb_vectors()
        kb_scored = []
        for entry, vec in zip(self._kb_entries, self._kb_vectors or []):
            score = _cosine_similarity(q_vec, vec) + 0.1 * _keyword_score(query, " ".join(entry["topics"]))
            kb_scored.append((score, entry["text"]))
        kb_scored.sort(key=lambda x: x[0], reverse=True)
        legal_hits = [t for s, t in kb_scored[:legal_top_k] if s > 0.05]
        if legal_hits:
            parts.append("LEGAL / MARKET CONTEXT:\n" + "\n---\n".join(legal_hits))

        return "\n\n".join(parts)

    def clear_document(self, document_id: str) -> None:
        self._doc_chunks.pop(document_id, None)


rag_service = RAGService()
