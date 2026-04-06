"""tests/unit/test_memory_service.py — Embedding + similarity scoring logic."""
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.memory_service import MemoryService


@pytest.fixture
def mock_memory_repo():
    repo = MagicMock()
    repo.upsert_memory = AsyncMock(return_value="point_abc123")
    repo.search_memories = AsyncMock(return_value=[])
    repo.list_user_memories = AsyncMock(return_value=[])
    repo.delete_memory = AsyncMock()
    repo.delete_all_user_memories = AsyncMock()
    return repo


@pytest.fixture
def mock_ai_service():
    svc = MagicMock()
    svc.json_completion = AsyncMock(
        return_value=json.dumps({
            "importance_score": 0.85,
            "topic_tags": ["career", "decision"],
            "emotional_tone": "anxious",
        })
    )
    return svc


@pytest.fixture
def memory_service(mock_memory_repo, mock_ai_service):
    return MemoryService(memory_repo=mock_memory_repo, ai_service=mock_ai_service)


class TestMemoryService:

    @pytest.mark.asyncio
    async def test_store_memory_calls_upsert(self, memory_service, mock_memory_repo):
        chat_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())

        point_id = await memory_service.store_memory(
            chat_id=chat_id,
            user_id=user_id,
            session_id=session_id,
            user_message="Should I take the job?",
            assistant_response="Based on your risk tolerance, yes.",
        )

        assert point_id == "point_abc123"
        mock_memory_repo.upsert_memory.assert_called_once()
        call_kwargs = mock_memory_repo.upsert_memory.call_args.kwargs
        assert call_kwargs["chat_id"] == chat_id
        assert call_kwargs["user_id"] == user_id
        assert call_kwargs["importance_score"] == 0.85
        assert "career" in call_kwargs["topic_tags"]
        assert call_kwargs["emotional_tone"] == "anxious"

    @pytest.mark.asyncio
    async def test_store_memory_uses_defaults_on_llm_failure(
        self, mock_memory_repo, mock_ai_service
    ):
        mock_ai_service.json_completion = AsyncMock(side_effect=Exception("LLM timeout"))
        svc = MemoryService(memory_repo=mock_memory_repo, ai_service=mock_ai_service)

        point_id = await svc.store_memory(
            chat_id=str(uuid.uuid4()),
            user_id=str(uuid.uuid4()),
            session_id=str(uuid.uuid4()),
            user_message="test",
            assistant_response="test reply",
        )

        # Should still complete with default importance
        assert point_id == "point_abc123"
        call_kwargs = mock_memory_repo.upsert_memory.call_args.kwargs
        assert call_kwargs["importance_score"] == 0.5  # default fallback

    @pytest.mark.asyncio
    async def test_retrieve_memories_delegates_to_repo(self, memory_service, mock_memory_repo, sample_memories):
        mock_memory_repo.search_memories = AsyncMock(return_value=sample_memories)

        results = await memory_service.retrieve_memories(
            user_id=str(uuid.uuid4()),
            query="career advice",
        )

        assert len(results) == 2
        assert results[0]["point_id"] == "abc123"
        mock_memory_repo.search_memories.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_memory_calls_repo(self, memory_service, mock_memory_repo):
        await memory_service.delete_memory("point_abc123")
        mock_memory_repo.delete_memory.assert_called_once_with("point_abc123")

    @pytest.mark.asyncio
    async def test_delete_all_calls_repo(self, memory_service, mock_memory_repo):
        user_id = str(uuid.uuid4())
        await memory_service.delete_all(user_id)
        mock_memory_repo.delete_all_user_memories.assert_called_once_with(user_id)
