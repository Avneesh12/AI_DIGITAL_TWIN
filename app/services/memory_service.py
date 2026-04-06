"""
app/services/memory_service.py
────────────────────────────────
Orchestrates memory persistence and retrieval.
Calls AIService for importance scoring at storage time.
"""
from __future__ import annotations

import json
from loguru import logger

from app.repositories.memory_repo import MemoryRepository
from app.services.ai_service import AIService
from app.services.prompt_builder import PromptBuilder


class MemoryService:
    def __init__(
        self,
        memory_repo: MemoryRepository,
        ai_service: AIService,
    ) -> None:
        self._repo = memory_repo
        self._ai = ai_service

    async def store_memory(
        self,
        chat_id: str,
        user_id: str,
        session_id: str,
        user_message: str,
        assistant_response: str,
    ) -> str:
        """
        Classify importance, extract tags, then upsert to Qdrant.
        Returns point_id.
        """
        importance_score = 0.5
        topic_tags: list[str] = []
        emotional_tone: str | None = None

        # Lightweight classification via LLM
        try:
            prompt = PromptBuilder.importance_scoring_prompt(user_message, assistant_response)
            raw = await self._ai.json_completion(prompt)
            # Strip any markdown fences just in case
            raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
            data = json.loads(raw)
            importance_score = float(data.get("importance_score", 0.5))
            topic_tags = data.get("topic_tags", [])
            emotional_tone = data.get("emotional_tone")
        except Exception as e:
            logger.warning("Importance scoring failed, using defaults", error=str(e))

        point_id = await self._repo.upsert_memory(
            chat_id=chat_id,
            user_id=user_id,
            session_id=session_id,
            user_message=user_message,
            assistant_response=assistant_response,
            topic_tags=topic_tags,
            emotional_tone=emotional_tone,
            importance_score=importance_score,
        )
        logger.debug("Memory stored", point_id=point_id, importance=importance_score)
        return point_id

    async def retrieve_memories(
        self,
        user_id: str,
        query: str,
    ) -> list[dict]:
        """Search Qdrant for the most relevant memories for this query."""
        return await self._repo.search_memories(user_id=user_id, query_text=query)

    async def list_memories(self, user_id: str, limit: int = 50) -> list[dict]:
        return await self._repo.list_user_memories(user_id=user_id, limit=limit)

    async def delete_memory(self, point_id: str) -> None:
        await self._repo.delete_memory(point_id)

    async def delete_all(self, user_id: str) -> None:
        await self._repo.delete_all_user_memories(user_id)
