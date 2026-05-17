"""
Real-time progress events for document analysis (SSE + status polling).
"""
from __future__ import annotations

import asyncio
import logging
from collections import deque
from datetime import datetime, timezone
from typing import Any, AsyncIterator

logger = logging.getLogger(__name__)

MAX_HISTORY = 100


class ProgressService:
    """Broadcasts pipeline progress to SSE subscribers per document."""

    def __init__(self):
        self._history: dict[str, deque[dict[str, Any]]] = {}
        self._latest: dict[str, dict[str, Any]] = {}
        self._queues: dict[str, list[asyncio.Queue]] = {}

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    async def emit(
        self,
        document_id: str,
        *,
        status: str,
        message: str,
        percent: int = 0,
        step: str = "",
        detail: str = "",
    ) -> None:
        event = {
            "type": "progress",
            "document_id": document_id,
            "status": status,
            "step": step,
            "message": message,
            "percent": max(0, min(100, percent)),
            "detail": detail,
            "timestamp": self._now(),
        }
        self._latest[document_id] = event
        if document_id not in self._history:
            self._history[document_id] = deque(maxlen=MAX_HISTORY)
        self._history[document_id].append(event)

        for queue in list(self._queues.get(document_id, [])):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass

    async def emit_complete(self, document_id: str, *, status: str = "completed", message: str = "Analysis complete") -> None:
        await self.emit(document_id, status=status, message=message, percent=100, step="done")

    async def emit_error(self, document_id: str, message: str) -> None:
        event = {
            "type": "error",
            "document_id": document_id,
            "status": "failed",
            "message": message,
            "percent": 0,
            "timestamp": self._now(),
        }
        self._latest[document_id] = event
        if document_id not in self._history:
            self._history[document_id] = deque(maxlen=MAX_HISTORY)
        self._history[document_id].append(event)
        for queue in list(self._queues.get(document_id, [])):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass

    def get_latest(self, document_id: str) -> dict[str, Any] | None:
        return self._latest.get(document_id)

    def get_history(self, document_id: str) -> list[dict[str, Any]]:
        return list(self._history.get(document_id, []))

    async def subscribe(self, document_id: str) -> AsyncIterator[dict[str, Any]]:
        queue: asyncio.Queue = asyncio.Queue(maxsize=50)
        self._queues.setdefault(document_id, []).append(queue)

        for past in self.get_history(document_id):
            yield past

        try:
            while True:
                event = await queue.get()
                yield event
                if event.get("type") == "error" or event.get("status") in ("completed", "failed"):
                    break
        finally:
            subs = self._queues.get(document_id, [])
            if queue in subs:
                subs.remove(queue)

    def clear(self, document_id: str) -> None:
        self._history.pop(document_id, None)
        self._latest.pop(document_id, None)
        self._queues.pop(document_id, None)


progress_service = ProgressService()
