"""
app/workers/personality_updater.py
────────────────────────────────────
Celery task for async personality auto-learning.
Can be invoked from the chat service as an alternative to asyncio.create_task
when you want durable, retriable background processing.

Usage (from celery worker):
    celery -A app.workers.personality_updater worker --loglevel=info
"""
from __future__ import annotations

import asyncio

from celery import Celery
from loguru import logger

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "digital_twin_workers",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
)


@celery_app.task(
    name="workers.update_personality",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def update_personality_task(self, user_id: str) -> dict:
    """
    Celery task: pull recent chats, extract personality traits via LLM,
    merge with existing profile.

    Runs in its own event loop since Celery workers are synchronous by default.
    """
    try:
        result = asyncio.run(_async_update_personality(user_id))
        logger.info("Personality task completed", user_id=user_id)
        return {"status": "ok", "user_id": user_id, "confidence": result}
    except Exception as exc:
        logger.error("Personality task failed", user_id=user_id, error=str(exc))
        raise self.retry(exc=exc)


async def _async_update_personality(user_id: str) -> float:
    """Async inner function that wires up the full service stack."""
    from app.core.database import AsyncSessionFactory
    from app.repositories.chat_repo import ChatRepository
    from app.repositories.personality_repo import PersonalityRepository
    from app.services.ai_service import AIService
    from app.services.personality_service import PersonalityService

    async with AsyncSessionFactory() as session:
        personality_repo = PersonalityRepository(session)
        chat_repo = ChatRepository(session)
        ai_service = AIService()

        svc = PersonalityService(
            personality_repo=personality_repo,
            chat_repo=chat_repo,
            ai_service=ai_service,
        )
        profile = await svc.auto_learn_from_chats(user_id)
        await session.commit()
        return profile.trait_confidence
