"""
app/services/chat_service.py
"""
from __future__ import annotations

import asyncio
import uuid

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.personality import PersonalityProfile
from app.models.user import User
from app.repositories.chat_repo import ChatRepository
from app.repositories.personality_repo import PersonalityRepository
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.ai_service import AIService
from app.services.memory_service import MemoryService
from app.services.personality_service import PersonalityService
from app.services.prompt_builder import PromptBuilder
from app.core.database import AsyncSessionFactory

PERSONALITY_UPDATE_THRESHOLD = 10


class ChatService:
    def __init__(
        self,
        chat_repo: ChatRepository,
        personality_repo: PersonalityRepository,
        memory_service: MemoryService,
        personality_service: PersonalityService,
        ai_service: AIService,
        prompt_builder: PromptBuilder,
    ) -> None:
        self._chat_repo = chat_repo
        self._personality_repo = personality_repo
        self._memory_svc = memory_service
        self._personality_svc = personality_service
        self._ai = ai_service
        self._prompt = prompt_builder

    async def handle(self, user: User, request: ChatRequest) -> ChatResponse:
        user_id = str(user.id)
        session_id = request.session_id or uuid.uuid4()

        logger.info("Chat pipeline start", user_id=user_id, session_id=str(session_id))

        # ── Phase 1: Load personality profile ──────────────────────────────
        profile = await self._personality_repo.get_by_user_id(user.id)
        if profile is None:
            profile = await self._personality_repo.create(user.id)

        # ── Phase 2: Memory retrieval (RAG) ────────────────────────────────
        memories = await self._memory_svc.retrieve_memories(
            user_id=user_id,
            query=request.message,
        )
        logger.debug("Memories retrieved", count=len(memories))

        # ── Phase 2b: Load recent session turns ────────────────────────────
        recent_turns = await self._load_session_turns(user.id, session_id)

        # ── Phase 3: Prompt construction ───────────────────────────────────
        messages = self._prompt.build_messages(
            username=user.username,
            profile=profile,
            memories=memories,
            user_message=request.message,
            recent_turns=recent_turns,
        )

        # ── Phase 4: LLM call ───────────────────────────────────────────────
        response_text, tokens_used = await self._ai.chat(messages)
        logger.debug("LLM response received", tokens=tokens_used)

        # ── Phase 5: Persist ────────────────────────────────────────────────
        memory_ids = [str(m.get("point_id", "")) for m in memories]

        user_chat = await self._chat_repo.create(
            user_id=user.id,
            session_id=session_id,
            role="user",
            content=request.message,
            tokens_used=0,
            memory_ids_used=[],
        )

        asst_chat = await self._chat_repo.create(
            user_id=user.id,
            session_id=session_id,
            role="assistant",
            content=response_text,
            tokens_used=tokens_used,
            memory_ids_used=memory_ids,
        )

        # ── Phase 5b: Store memory vector (fire and forget) ─────────────────
        asyncio.create_task(
            self._store_memory_async(
                chat_id=str(asst_chat.id),
                user_id=user_id,
                session_id=str(session_id),
                user_message=request.message,
                assistant_response=response_text,
            )
        )

        # ── Phase 5c: Maybe trigger personality update ──────────────────────
        asyncio.create_task(
            self._maybe_update_personality(user_id=user_id)
        )

        return ChatResponse(
            response=response_text,
            session_id=str(session_id),
            chat_id=str(asst_chat.id),
            memories_used=len(memories),
            tokens_used=tokens_used,
        )

    # ── Private Helpers ───────────────────────────────────────────────────

    async def _load_session_turns(
        self, user_id: uuid.UUID, session_id: uuid.UUID
    ) -> list[dict]:
        chats = await self._chat_repo.get_session_history(
            user_id=user_id, session_id=session_id, limit=20
        )
        return [{"role": c.role, "content": c.content} for c in chats]

    async def _store_memory_async(
        self,
        chat_id: str,
        user_id: str,
        session_id: str,
        user_message: str,
        assistant_response: str,
    ) -> None:
        try:
            await self._memory_svc.store_memory(
                chat_id=chat_id,
                user_id=user_id,
                session_id=session_id,
                user_message=user_message,
                assistant_response=assistant_response,
            )
        except Exception as e:
            logger.error("Background memory storage failed", error=str(e))

    async def _maybe_update_personality(self, user_id: str) -> None:
        try:
            uid = uuid.UUID(user_id)
            
            async with AsyncSessionFactory() as session:  # ← own fresh session
                try:
                    bg_chat_repo = ChatRepository(session)
                    count = await bg_chat_repo.count_user_chats(uid)
                    await session.commit()
                except Exception:
                    await session.rollback()
                    raise

            if count > 0 and count % PERSONALITY_UPDATE_THRESHOLD == 0:
                logger.info("Triggering personality auto-learn", user_id=user_id, chat_count=count)
                await self._personality_svc.auto_learn_from_chats(user_id)

        except Exception:
            logger.exception("Background personality update failed")