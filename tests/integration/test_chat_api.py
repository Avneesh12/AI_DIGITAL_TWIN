"""
tests/integration/test_chat_api.py
────────────────────────────────────
Integration tests for the /chat endpoint.
Mocks LLM and Qdrant — tests the full pipeline wiring.
"""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.security import create_access_token
from app.models.personality import PersonalityProfile
from app.models.user import User


def _auth_headers(user_id: str) -> dict:
    token = create_access_token(user_id)
    return {"Authorization": f"Bearer {token}"}


def _make_user(user_id: str) -> User:
    u = MagicMock(spec=User)
    u.id = uuid.UUID(user_id)
    u.username = "alice"
    u.email = "alice@example.com"
    u.is_active = True
    return u


def _make_profile(user_id: str) -> PersonalityProfile:
    p = MagicMock(spec=PersonalityProfile)
    p.user_id = uuid.UUID(user_id)
    p.tone = "casual"
    p.communication_style = "direct"
    p.values = ["honesty"]
    p.interests = ["tech"]
    p.decision_style = "analytical"
    p.openness = 0.7
    p.conscientiousness = 0.7
    p.extraversion = 0.5
    p.agreeableness = 0.5
    p.neuroticism = 0.3
    p.persona_summary = "A direct and honest thinker."
    p.trait_confidence = 0.5
    return p


def _make_chat(user_id: str, session_id: str) -> MagicMock:
    chat = MagicMock()
    chat.id = uuid.uuid4()
    chat.user_id = uuid.UUID(user_id)
    chat.session_id = uuid.UUID(session_id)
    chat.role = "assistant"
    chat.content = "Here is my response."
    return chat


class TestChatEndpoint:

    @pytest.mark.asyncio
    async def test_chat_unauthenticated_returns_403(self, async_client):
        resp = await async_client.post("/api/v1/chat", json={"message": "Hello"})
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_chat_returns_response(self, async_client):
        user_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())
        mock_user = _make_user(user_id)
        mock_profile = _make_profile(user_id)
        mock_chat = _make_chat(user_id, session_id)

        with (
            patch("app.dependencies.get_current_user", return_value=mock_user),
            patch("app.repositories.personality_repo.PersonalityRepository.get_by_user_id",
                  new_callable=AsyncMock, return_value=mock_profile),
            patch("app.repositories.memory_repo.MemoryRepository.search_memories",
                  new_callable=AsyncMock, return_value=[]),
            patch("app.repositories.chat_repo.ChatRepository.get_session_history",
                  new_callable=AsyncMock, return_value=[]),
            patch("app.services.ai_service.AIService.chat",
                  new_callable=AsyncMock, return_value=("Here's what I think about that.", 42)),
            patch("app.repositories.chat_repo.ChatRepository.create",
                  new_callable=AsyncMock, return_value=mock_chat),
            patch("app.services.memory_service.MemoryService.store_memory",
                  new_callable=AsyncMock, return_value="point_xyz"),
            patch("app.repositories.chat_repo.ChatRepository.count_user_chats",
                  new_callable=AsyncMock, return_value=5),
        ):
            resp = await async_client.post(
                "/api/v1/chat",
                json={"message": "What should I do about the job offer?"},
                headers=_auth_headers(user_id),
            )

        assert resp.status_code == 200
        body = resp.json()
        assert "response" in body
        assert "session_id" in body
        assert "chat_id" in body
        assert "tokens_used" in body
        assert body["tokens_used"] == 42

    @pytest.mark.asyncio
    async def test_chat_empty_message_fails_validation(self, async_client):
        user_id = str(uuid.uuid4())
        resp = await async_client.post(
            "/api/v1/chat",
            json={"message": ""},
            headers=_auth_headers(user_id),
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_chat_creates_new_profile_for_new_user(self, async_client):
        """When no personality profile exists, one should be created on first chat."""
        user_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())
        mock_user = _make_user(user_id)
        blank_profile = _make_profile(user_id)
        mock_chat = _make_chat(user_id, session_id)

        with (
            patch("app.dependencies.get_current_user", return_value=mock_user),
            # Return None first (no profile), then create one
            patch("app.repositories.personality_repo.PersonalityRepository.get_by_user_id",
                  new_callable=AsyncMock, return_value=None),
            patch("app.repositories.personality_repo.PersonalityRepository.create",
                  new_callable=AsyncMock, return_value=blank_profile),
            patch("app.repositories.memory_repo.MemoryRepository.search_memories",
                  new_callable=AsyncMock, return_value=[]),
            patch("app.repositories.chat_repo.ChatRepository.get_session_history",
                  new_callable=AsyncMock, return_value=[]),
            patch("app.services.ai_service.AIService.chat",
                  new_callable=AsyncMock, return_value=("My first response.", 10)),
            patch("app.repositories.chat_repo.ChatRepository.create",
                  new_callable=AsyncMock, return_value=mock_chat),
            patch("app.services.memory_service.MemoryService.store_memory",
                  new_callable=AsyncMock, return_value="point_new"),
            patch("app.repositories.chat_repo.ChatRepository.count_user_chats",
                  new_callable=AsyncMock, return_value=1),
        ):
            resp = await async_client.post(
                "/api/v1/chat",
                json={"message": "Hello, who am I?"},
                headers=_auth_headers(user_id),
            )

        assert resp.status_code == 200
