"""tests/conftest.py — Shared pytest fixtures for unit + integration tests."""
import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.models.personality import PersonalityProfile
from app.models.user import User


# ── App ───────────────────────────────────────────────────────────────────────

@pytest.fixture
def app():
    return create_app()


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest_asyncio.fixture
async def async_client(app) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# ── Domain Objects ────────────────────────────────────────────────────────────

@pytest.fixture
def sample_user_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def sample_user(sample_user_id) -> User:
    user = MagicMock(spec=User)
    user.id = uuid.UUID(sample_user_id)
    user.username = "testuser"
    user.email = "test@example.com"
    user.is_active = True
    return user


@pytest.fixture
def sample_personality(sample_user_id) -> PersonalityProfile:
    profile = MagicMock(spec=PersonalityProfile)
    profile.id = uuid.uuid4()
    profile.user_id = uuid.UUID(sample_user_id)
    profile.tone = "casual"
    profile.communication_style = "concise and direct"
    profile.values = ["honesty", "efficiency"]
    profile.interests = ["technology", "philosophy"]
    profile.decision_style = "analytical"
    profile.openness = 0.8
    profile.conscientiousness = 0.7
    profile.extraversion = 0.4
    profile.agreeableness = 0.6
    profile.neuroticism = 0.3
    profile.persona_summary = "A pragmatic technologist who values clear thinking."
    profile.trait_confidence = 0.6
    return profile


@pytest.fixture
def sample_memories() -> list[dict]:
    return [
        {
            "point_id": "abc123",
            "score": 0.91,
            "cosine_score": 0.88,
            "user_message": "Should I take the job offer at the startup?",
            "assistant_response": "Given my risk tolerance and financial situation, I'd take it.",
            "topic_tags": ["career", "decision"],
            "emotional_tone": "anxious",
            "importance_score": 0.85,
            "created_at": "2025-01-01T10:00:00Z",
        },
        {
            "point_id": "def456",
            "score": 0.84,
            "cosine_score": 0.80,
            "user_message": "How do I handle disagreements at work?",
            "assistant_response": "I prefer to address things directly but calmly.",
            "topic_tags": ["work", "communication"],
            "emotional_tone": "neutral",
            "importance_score": 0.6,
            "created_at": "2025-01-05T14:00:00Z",
        },
    ]
