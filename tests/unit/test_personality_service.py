"""tests/unit/test_personality_service.py — Trait extraction and merging logic."""
import json
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.personality import PersonalityProfile
from app.services.personality_service import PersonalityService


@pytest.fixture
def mock_personality_repo():
    repo = MagicMock()
    repo.get_by_user_id = AsyncMock(return_value=None)
    repo.create = AsyncMock()
    repo.update = AsyncMock()
    repo.upsert = AsyncMock()
    return repo


@pytest.fixture
def mock_chat_repo():
    repo = MagicMock()
    repo.get_recent_chats = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def mock_ai_service():
    svc = MagicMock()
    svc.json_completion = AsyncMock(
        return_value=json.dumps({
            "tone": "analytical",
            "communication_style": "verbose and structured",
            "values": ["precision", "integrity"],
            "interests": ["machine learning", "stoicism"],
            "decision_style": "data-driven",
            "openness": 0.9,
            "conscientiousness": 0.85,
            "extraversion": 0.3,
            "agreeableness": 0.5,
            "neuroticism": 0.2,
            "persona_summary": "A methodical thinker who values evidence over intuition.",
        })
    )
    return svc


@pytest.fixture
def personality_service(mock_personality_repo, mock_chat_repo, mock_ai_service):
    return PersonalityService(
        personality_repo=mock_personality_repo,
        chat_repo=mock_chat_repo,
        ai_service=mock_ai_service,
    )


class TestPersonalityService:

    @pytest.mark.asyncio
    async def test_auto_learn_skips_when_too_few_chats(
        self, personality_service, mock_chat_repo, mock_ai_service
    ):
        """Should not call LLM when fewer than 5 chats."""
        mock_chat_repo.get_recent_chats = AsyncMock(return_value=[MagicMock() for _ in range(3)])
        mock_personality_repo = personality_service._repo
        mock_personality_repo.get_by_user_id = AsyncMock(return_value=MagicMock(spec=PersonalityProfile))

        await personality_service.auto_learn_from_chats(str(uuid.uuid4()))
        mock_ai_service.json_completion.assert_not_called()

    @pytest.mark.asyncio
    async def test_auto_learn_merges_big_five_weighted(
        self, mock_personality_repo, mock_chat_repo, mock_ai_service
    ):
        """
        Existing profile with confidence=0.0 should heavily weight LLM result (new_weight=0.7).
        openness: existing=0.5, extracted=0.9 → expected ≈ 0.5*0.3 + 0.9*0.7 = 0.78
        """
        existing = MagicMock(spec=PersonalityProfile)
        existing.trait_confidence = 0.0
        existing.openness = 0.5
        existing.conscientiousness = 0.5
        existing.extraversion = 0.5
        existing.agreeableness = 0.5
        existing.neuroticism = 0.5
        existing.values = []
        existing.interests = []
        mock_personality_repo.get_by_user_id = AsyncMock(return_value=existing)
        mock_chat_repo.get_recent_chats = AsyncMock(
            return_value=[MagicMock(role="user", content=f"msg {i}") for i in range(10)]
        )

        captured_kwargs = {}

        async def capture_update(profile, **kwargs):
            captured_kwargs.update(kwargs)
            updated = MagicMock(spec=PersonalityProfile)
            updated.trait_confidence = kwargs.get("trait_confidence", 0.0)
            return updated

        mock_personality_repo.update = capture_update

        svc = PersonalityService(
            personality_repo=mock_personality_repo,
            chat_repo=mock_chat_repo,
            ai_service=mock_ai_service,
        )
        await svc.auto_learn_from_chats(str(uuid.uuid4()))

        expected_openness = round(0.5 * 0.3 + 0.9 * 0.7, 4)
        assert abs(captured_kwargs.get("openness", 0) - expected_openness) < 0.001

    @pytest.mark.asyncio
    async def test_auto_learn_grows_confidence(
        self, mock_personality_repo, mock_chat_repo, mock_ai_service
    ):
        existing = MagicMock(spec=PersonalityProfile)
        existing.trait_confidence = 0.4
        existing.values = []
        existing.interests = []
        for trait in ["openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"]:
            setattr(existing, trait, 0.5)
        mock_personality_repo.get_by_user_id = AsyncMock(return_value=existing)
        mock_chat_repo.get_recent_chats = AsyncMock(
            return_value=[MagicMock(role="user", content=f"msg {i}") for i in range(10)]
        )

        captured_kwargs = {}
        async def capture(profile, **kwargs):
            captured_kwargs.update(kwargs)
            result = MagicMock(spec=PersonalityProfile)
            result.trait_confidence = kwargs["trait_confidence"]
            return result
        mock_personality_repo.update = capture

        svc = PersonalityService(
            personality_repo=mock_personality_repo,
            chat_repo=mock_chat_repo,
            ai_service=mock_ai_service,
        )
        await svc.auto_learn_from_chats(str(uuid.uuid4()))

        # Confidence should increase by 0.05
        assert abs(captured_kwargs["trait_confidence"] - 0.45) < 0.001

    @pytest.mark.asyncio
    async def test_auto_learn_deduplicates_values(
        self, mock_personality_repo, mock_chat_repo, mock_ai_service
    ):
        existing = MagicMock(spec=PersonalityProfile)
        existing.trait_confidence = 0.2
        existing.values = ["honesty", "precision"]    # "precision" already exists
        existing.interests = []
        for trait in ["openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"]:
            setattr(existing, trait, 0.5)
        mock_personality_repo.get_by_user_id = AsyncMock(return_value=existing)
        mock_chat_repo.get_recent_chats = AsyncMock(
            return_value=[MagicMock(role="user", content=f"msg {i}") for i in range(10)]
        )

        captured_kwargs = {}
        async def capture(profile, **kwargs):
            captured_kwargs.update(kwargs)
            result = MagicMock(spec=PersonalityProfile)
            result.trait_confidence = kwargs.get("trait_confidence", 0.2)
            return result
        mock_personality_repo.update = capture

        svc = PersonalityService(
            personality_repo=mock_personality_repo,
            chat_repo=mock_chat_repo,
            ai_service=mock_ai_service,
        )
        await svc.auto_learn_from_chats(str(uuid.uuid4()))

        merged_values = captured_kwargs.get("values", [])
        # "precision" appears in both → should appear only once
        assert merged_values.count("precision") == 1
