"""
app/repositories/memory_repo.py
────────────────────────────────
Qdrant vector operations: upsert, search, delete.
All operations are scoped per-user via payload filtering.
"""
from __future__ import annotations

import math
from datetime import UTC, datetime

from loguru import logger
from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import PointStruct, UpdateStatus

from app.config import get_settings
from app.core.embedder import Embedder, deterministic_point_id
from app.core.exceptions import VectorStoreError
from app.core.qdrant_client import build_user_filter

settings = get_settings()

COLLECTION = settings.QDRANT_COLLECTION


class MemoryRepository:
    def __init__(self, client: AsyncQdrantClient, embedder: Embedder) -> None:
        self._client = client
        self._embedder = embedder

    # ── Write ─────────────────────────────────────────────────────────────

    async def upsert_memory(
        self,
        chat_id: str,
        user_id: str,
        session_id: str,
        user_message: str,
        assistant_response: str,
        topic_tags: list[str] | None = None,
        emotional_tone: str | None = None,
        importance_score: float = 0.5,
    ) -> str:
        """
        Embed (user_message + assistant_response) and upsert into Qdrant.
        Uses deterministic point ID derived from chat_id for idempotency.
        Returns the point_id.
        """
        vector = await self._embedder.embed_pair(user_message, assistant_response)
        point_id = deterministic_point_id(chat_id)

        payload = {
            "user_id": user_id,
            "session_id": session_id,
            "chat_id": chat_id,
            "user_message": user_message,
            "assistant_response": assistant_response,
            "topic_tags": topic_tags or [],
            "emotional_tone": emotional_tone,
            "importance_score": importance_score,
            "created_at": datetime.now(UTC).isoformat(),
            "access_count": 0,
        }

        try:
            result = await self._client.upsert(
                collection_name=COLLECTION,
                points=[PointStruct(id=point_id, vector=vector, payload=payload)],
            )
            if result.status != UpdateStatus.COMPLETED:
                raise VectorStoreError(detail=f"Upsert status: {result.status}")
            return point_id
        except VectorStoreError:
            raise
        except Exception as e:
            raise VectorStoreError(detail=str(e)) from e

    # ── Search ────────────────────────────────────────────────────────────

    async def search_memories(
        self,
        user_id: str,
        query_text: str,
        top_k: int | None = None,
        score_threshold: float | None = None,
    ) -> list[dict]:
        """
        Embed query_text and retrieve top-K similar memories for the user.

        Scoring formula:
            final_score = cosine * 0.6 + recency_weight * 0.25 + importance * 0.15

        Returns list of payload dicts enriched with composite score.
        """
        k = top_k or settings.MEMORY_TOP_K
        threshold = score_threshold or settings.MEMORY_SCORE_THRESHOLD

        vector = await self._embedder.embed(query_text)

        try:
            results = await self._client.search(
                collection_name=COLLECTION,
                query_vector=vector,
                query_filter=build_user_filter(user_id),
                limit=k * 2,  # Fetch more, re-rank, then trim
                score_threshold=threshold,
                with_payload=True,
            )
        except Exception as e:
            raise VectorStoreError(detail=str(e)) from e

        enriched = []
        now = datetime.now(UTC)

        for hit in results:
            payload = hit.payload or {}
            cosine = hit.score

            # Recency weight: decays logarithmically
            try:
                created = datetime.fromisoformat(payload.get("created_at", now.isoformat()))
                days_old = max(0, (now - created.replace(tzinfo=UTC)).days)
                recency = 1.0 / (1.0 + math.log(days_old + 1))
            except Exception:
                recency = 0.5

            importance = float(payload.get("importance_score", 0.5))
            composite = cosine * 0.6 + recency * 0.25 + importance * 0.15

            enriched.append({
                "point_id": hit.id,
                "score": round(composite, 4),
                "cosine_score": round(cosine, 4),
                **payload,
            })

        # Sort by composite score, take top_k
        enriched.sort(key=lambda x: x["score"], reverse=True)
        return enriched[:k]

    # ── Delete ────────────────────────────────────────────────────────────

    async def delete_memory(self, point_id: str) -> None:
        try:
            await self._client.delete(
                collection_name=COLLECTION,
                points_selector=[point_id],
            )
        except Exception as e:
            raise VectorStoreError(detail=str(e)) from e

    async def delete_all_user_memories(self, user_id: str) -> None:
        try:
            await self._client.delete(
                collection_name=COLLECTION,
                points_selector=build_user_filter(user_id),  # type: ignore
            )
        except Exception as e:
            raise VectorStoreError(detail=str(e)) from e

    async def list_user_memories(self, user_id: str, limit: int = 50) -> list[dict]:
        try:
            results, _ = await self._client.scroll(
                collection_name=COLLECTION,
                scroll_filter=build_user_filter(user_id),
                limit=limit,
                with_payload=True,
            )
            return [{"point_id": r.id, **(r.payload or {})} for r in results]
        except Exception as e:
            raise VectorStoreError(detail=str(e)) from e
