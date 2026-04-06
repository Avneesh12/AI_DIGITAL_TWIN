"""app/repositories/chat_repo.py — Chat history queries."""
import uuid

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import Chat


class ChatRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        role: str,
        content: str,
        tokens_used: int = 0,
        memory_ids_used: list | None = None,
    ) -> Chat:
        chat = Chat(
            user_id=user_id,
            session_id=session_id,
            role=role,
            content=content,
            tokens_used=tokens_used,
            memory_ids_used=memory_ids_used or [],
        )
        self._session.add(chat)
        await self._session.flush()
        await self._session.refresh(chat)
        return chat

    async def get_session_history(
        self, user_id: uuid.UUID, session_id: uuid.UUID, limit: int = 20
    ) -> list[Chat]:
        result = await self._session.execute(
            select(Chat)
            .where(Chat.user_id == user_id, Chat.session_id == session_id)
            .order_by(Chat.created_at)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_user_chats(self, user_id: uuid.UUID) -> int:
        from sqlalchemy import func
        result = await self._session.execute(
            select(func.count(Chat.id)).where(Chat.user_id == user_id)
        )
        return result.scalar_one()

    async def get_recent_chats(self, user_id: uuid.UUID, limit: int = 20) -> list[Chat]:
        result = await self._session.execute(
            select(Chat)
            .where(Chat.user_id == user_id)
            .order_by(desc(Chat.created_at))
            .limit(limit)
        )
        return list(result.scalars().all())
