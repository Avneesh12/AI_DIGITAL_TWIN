"""app/repositories/personality_repo.py — Personality profile CRUD."""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.personality import PersonalityProfile


class PersonalityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, user_id: uuid.UUID, **kwargs) -> PersonalityProfile:
        profile = PersonalityProfile(user_id=user_id, **kwargs)
        self._session.add(profile)
        await self._session.flush()
        await self._session.refresh(profile)
        return profile

    async def get_by_user_id(self, user_id: uuid.UUID) -> PersonalityProfile | None:
        result = await self._session.execute(
            select(PersonalityProfile).where(PersonalityProfile.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def update(self, profile: PersonalityProfile, **kwargs) -> PersonalityProfile:
        for key, value in kwargs.items():
            if value is not None and hasattr(profile, key):
                setattr(profile, key, value)
        await self._session.flush()
        await self._session.refresh(profile)
        return profile

    async def upsert(self, user_id: uuid.UUID, **kwargs) -> PersonalityProfile:
        profile = await self.get_by_user_id(user_id)
        if profile is None:
            return await self.create(user_id, **kwargs)
        return await self.update(profile, **kwargs)
