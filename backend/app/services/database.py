"""
Database Service — Firestore → MongoDB → In-Memory priority chain.
Automatically picks the best available backend.
"""
import logging
from datetime import datetime
from typing import Optional

from app.models.schemas import DocumentRecord, DocumentListItem, DocumentStatus

logger = logging.getLogger(__name__)


class DatabaseService:
    """
    Multi-backend document store.
    Priority: Google Cloud Firestore → MongoDB (motor) → In-Memory dict.
    """

    def __init__(self):
        self._memory_store: dict[str, dict] = {}
        self._mongo_client = None
        self._mongo_db = None
        self._firestore = None
        self._initialized = False
        self._backend = "memory"  # 'firestore' | 'mongodb' | 'memory'

    async def initialize(self):
        if self._initialized:
            return

        # ── Try Firestore first ───────────────────────────────────────────
        try:
            from app.services.firestore_service import firestore_service
            if firestore_service.is_available:
                self._firestore = firestore_service
                self._backend = "firestore"
                logger.info("✅ Database: Google Cloud Firestore")
                self._initialized = True
                return
        except Exception as e:
            logger.debug(f"Firestore init skipped: {e}")

        # ── Try MongoDB ───────────────────────────────────────────────────
        try:
            from motor.motor_asyncio import AsyncIOMotorClient
            from app.core.config import settings

            client = AsyncIOMotorClient(settings.MONGODB_URL, serverSelectionTimeoutMS=3000)
            await client.admin.command("ping")
            self._mongo_client = client
            self._mongo_db = client[settings.MONGODB_DB_NAME]
            self._backend = "mongodb"
            logger.info("✅ Database: MongoDB")
            self._initialized = True
            return
        except Exception as e:
            logger.warning(f"MongoDB unavailable ({e})")

        # ── In-memory fallback ────────────────────────────────────────────
        logger.warning("⚠️  Database: In-Memory (data lost on restart). Configure Firestore or MongoDB for persistence.")
        self._backend = "memory"
        self._initialized = True

    async def save_document(self, doc: DocumentRecord) -> str:
        doc_dict = doc.model_dump(mode="json")

        if self._backend == "firestore" and self._firestore:
            try:
                await self._firestore.save(doc)
                return doc.id
            except Exception as e:
                logger.error(f"Firestore save failed, falling back to memory: {e}")

        if self._backend == "mongodb" and self._mongo_db is not None:
            try:
                await self._mongo_db.documents.update_one(
                    {"id": doc.id}, {"$set": doc_dict}, upsert=True
                )
                return doc.id
            except Exception as e:
                logger.error(f"MongoDB save failed, falling back to memory: {e}")

        self._memory_store[doc.id] = doc_dict
        return doc.id

    async def get_document(self, doc_id: str) -> Optional[dict]:
        if self._backend == "firestore" and self._firestore:
            try:
                return await self._firestore.get(doc_id)
            except Exception as e:
                logger.error(f"Firestore get failed: {e}")

        if self._backend == "mongodb" and self._mongo_db is not None:
            try:
                doc = await self._mongo_db.documents.find_one({"id": doc_id})
                if doc:
                    doc.pop("_id", None)
                    return doc
            except Exception as e:
                logger.error(f"MongoDB get failed: {e}")

        return self._memory_store.get(doc_id)

    async def list_documents(self, limit: int = 50, skip: int = 0) -> list[dict]:
        if self._backend == "firestore" and self._firestore:
            try:
                return await self._firestore.list(limit=limit, skip=skip)
            except Exception as e:
                logger.error(f"Firestore list failed: {e}")

        if self._backend == "mongodb" and self._mongo_db is not None:
            try:
                cursor = self._mongo_db.documents.find(
                    {}, {"raw_text": 0, "normalized_text": 0}
                ).sort("upload_date", -1).skip(skip).limit(limit)
                docs = []
                async for doc in cursor:
                    doc.pop("_id", None)
                    docs.append(doc)
                return docs
            except Exception as e:
                logger.error(f"MongoDB list failed: {e}")

        docs = list(self._memory_store.values())
        docs.sort(key=lambda d: d.get("upload_date", ""), reverse=True)
        return docs[skip: skip + limit]

    async def delete_document(self, doc_id: str) -> bool:
        if self._backend == "firestore" and self._firestore:
            try:
                return await self._firestore.delete(doc_id)
            except Exception as e:
                logger.error(f"Firestore delete failed: {e}")

        if self._backend == "mongodb" and self._mongo_db is not None:
            try:
                result = await self._mongo_db.documents.delete_one({"id": doc_id})
                return result.deleted_count > 0
            except Exception as e:
                logger.error(f"MongoDB delete failed: {e}")

        if doc_id in self._memory_store:
            del self._memory_store[doc_id]
            return True
        return False

    async def update_status(self, doc_id: str, status: DocumentStatus, error: str = None):
        update = {"status": status.value}
        if error:
            update["error_message"] = error

        if self._backend == "firestore" and self._firestore:
            try:
                from google.cloud import firestore
                from app.core.config import settings
                coll = self._firestore._collection
                if coll:
                    await coll.document(doc_id).update(update)
                    return
            except Exception as e:
                logger.error(f"Firestore status update failed: {e}")

        if self._backend == "mongodb" and self._mongo_db is not None:
            try:
                await self._mongo_db.documents.update_one(
                    {"id": doc_id}, {"$set": update}
                )
                return
            except Exception as e:
                logger.error(f"MongoDB status update failed: {e}")

        if doc_id in self._memory_store:
            self._memory_store[doc_id].update(update)

    @property
    def backend(self) -> str:
        return self._backend


db_service = DatabaseService()
