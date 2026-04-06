"""
app/services/personality_service.py
─────────────────────────────────────
Manages personality profiles.
Auto-learning merges LLM-extracted traits with existing profile
using a weighted average that grows more conservative as confidence rises.
"""
from __future__ import annotations

import json

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.personality import PersonalityProfile
from app.repositories.chat_repo import ChatRepository
from app.repositories.personality_repo import PersonalityRepository
from app.schemas.personality import PersonalityCreate, PersonalityUpdate
from app.services.ai_service import AIService
from app.services.prompt_builder import PromptBuilder

# Big Five trait field names
_BIG_FIVE = ["openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"]


class PersonalityService:
    def __init__(
        self,
        personality_repo: PersonalityRepository,
        chat_repo: ChatRepository,
        ai_service: AIService,
    ) -> None:
        self._repo = personality_repo
        self._chat_repo = chat_repo
        self._ai = ai_service

    async def get_or_create(self, user_id: str, session: AsyncSession) -> PersonalityProfile:
        """Return existing profile or create a blank one."""
        import uuid
        profile = await self._repo.get_by_user_id(uuid.UUID(user_id))
        if profile is None:
            profile = await self._repo.create(uuid.UUID(user_id))
        return profile

    async def create_profile(
        self,
        user_id: str,
        data: PersonalityCreate,
    ) -> PersonalityProfile:
        import uuid
        return await self._repo.upsert(
            uuid.UUID(user_id),
            **data.model_dump(exclude_none=True),
        )

    async def update_profile(
        self,
        user_id: str,
        data: PersonalityUpdate,
    ) -> PersonalityProfile:
        import uuid
        profile = await self._repo.get_by_user_id(uuid.UUID(user_id))
        if profile is None:
            from app.core.exceptions import NotFoundError
            raise NotFoundError("Personality profile not found")
        return await self._repo.update(profile, **data.model_dump(exclude_none=True))

    async def auto_learn_from_chats(self, user_id: str) -> PersonalityProfile:
        """
        Pull recent chats, extract traits via LLM, merge with existing profile.
        Called by background worker every N conversations.

        Merge strategy:
        - New profiles (confidence < 0.3): LLM result has high weight (0.7)
        - Established profiles (confidence >= 0.3): LLM result has lower weight (0.3)
          This prevents noisy data from destabilizing a well-calibrated profile.
        """
        import uuid
        uid = uuid.UUID(user_id)

        # Fetch recent chats for analysis
        recent = await self._chat_repo.get_recent_chats(uid, limit=30)
        if len(recent) < 5:
            logger.info("Not enough chats for auto-learning", user_id=user_id)
            return await self._repo.get_by_user_id(uid)

        # Format chats as a readable transcript
        transcript = "\n".join(
            f"[{c.role.upper()}]: {c.content[:300]}" for c in recent
        )

        # LLM extraction
        extracted: dict = {}
        try:
            prompt = PromptBuilder.personality_extraction_prompt(transcript)
            raw = await self._ai.json_completion(prompt, temperature=0.1, max_tokens=512)
            raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
            extracted = json.loads(raw)
        except Exception as e:
            logger.warning("Personality extraction failed", error=str(e))
            return await self._repo.get_by_user_id(uid)

        # Merge
        profile = await self._repo.get_by_user_id(uid)
        if profile is None:
            profile = await self._repo.create(uid)

        confidence = profile.trait_confidence
        new_weight = 0.7 if confidence < 0.3 else 0.3
        old_weight = 1.0 - new_weight

        update_kwargs: dict = {}

        # Merge Big Five numerics
        for trait in _BIG_FIVE:
            if trait in extracted:
                try:
                    new_val = float(extracted[trait])
                    old_val = getattr(profile, trait, 0.5)
                    merged = round(old_weight * old_val + new_weight * new_val, 4)
                    update_kwargs[trait] = max(0.0, min(1.0, merged))
                except (TypeError, ValueError):
                    pass

        # Merge categorical fields (overwrite only if LLM is confident)
        for field in ["tone", "communication_style", "decision_style", "persona_summary"]:
            if extracted.get(field):
                update_kwargs[field] = extracted[field]

        # Merge list fields — union (deduplicated)
        for field in ["values", "interests"]:
            if extracted.get(field):
                existing = list(getattr(profile, field) or [])
                incoming = list(extracted[field])
                merged_list = list(dict.fromkeys(existing + incoming))  # preserve order, dedupe
                update_kwargs[field] = merged_list[:20]  # Cap at 20 items

        # Grow confidence (asymptotic approach to 1.0)
        new_confidence = min(1.0, confidence + 0.05)
        update_kwargs["trait_confidence"] = new_confidence

        updated = await self._repo.update(profile, **update_kwargs)
        logger.info(
            "Personality auto-updated",
            user_id=user_id,
            confidence=new_confidence,
            traits_updated=list(update_kwargs.keys()),
        )
        return updated
