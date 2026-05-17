"""
Firestore Database Service for LexGuard.
Replaces / supplements MongoDB with Google Cloud Firestore.
Priority: Firestore → MongoDB (motor) → In-Memory.
"""
import logging
from datetime import datetime
from typing import Optional

from app.models.schemas import DocumentRecord, DocumentStatus
from app.core.config import settings

logger = logging.getLogger(__name__)


class FirestoreService:
    """
    Firestore-backed document storage.
    Uses the native Firestore client when GOOGLE_CLOUD_PROJECT is set.
    Otherwise defers to MongoDB / in-memory fallback.
    """

    def __init__(self):
        self._client = None
        self._collection = None
        self._initialized = False
        self._available = False

    def _init(self):
        if self._initialized:
            return
        self._initialized = True

        project = settings.GOOGLE_CLOUD_PROJECT
        if not project:
            logger.info("GOOGLE_CLOUD_PROJECT not set — Firestore disabled")
            return

        try:
            from google.cloud import firestore
            self._client = firestore.AsyncClient(project=project)
            self._collection = self._client.collection(
                settings.FIRESTORE_COLLECTION
            )
            self._available = True
            logger.info(
                f"✅ Firestore connected: project={project}, "
                f"collection={settings.FIRESTORE_COLLECTION}"
            )
        except Exception as e:
            logger.warning(f"Firestore unavailable ({e}) — using MongoDB/memory fallback")
            self._available = False

    @property
    def is_available(self) -> bool:
        self._init()
        return self._available

    async def save(self, doc: DocumentRecord) -> str:
        """Upsert a document record to Firestore."""
        self._init()
        if not self._available or self._collection is None:
            raise RuntimeError("Firestore not available")

        data = doc.model_dump(mode="json")
        await self._collection.document(doc.id).set(data, merge=True)
        return doc.id

    async def get(self, doc_id: str) -> Optional[dict]:
        """Retrieve a document by ID."""
        self._init()
        if not self._available or self._collection is None:
            raise RuntimeError("Firestore not available")

        snap = await self._collection.document(doc_id).get()
        if snap.exists:
            data = snap.to_dict()
            data.pop("_id", None)
            return data
        return None

    async def list(self, limit: int = 50, skip: int = 0) -> list[dict]:
        """List documents sorted by upload_date desc."""
        self._init()
        if not self._available or self._collection is None:
            raise RuntimeError("Firestore not available")

        query = (
            self._collection
            .order_by("upload_date", direction="DESCENDING")
            .limit(limit)
        )
        docs = []
        async for snap in query.stream():
            d = snap.to_dict()
            d.pop("_id", None)
            # Skip raw text fields for list view
            d.pop("raw_text", None)
            d.pop("normalized_text", None)
            docs.append(d)
        return docs[skip:]

    async def delete(self, doc_id: str) -> bool:
        """Delete a document."""
        self._init()
        if not self._available or self._collection is None:
            return False
        await self._collection.document(doc_id).delete()
        return True


firestore_service = FirestoreService()
