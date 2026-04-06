"""
app/dependencies.py
────────────────────
All shared FastAPI Depends() providers.
The dependency graph flows strictly downward:
  HTTP layer → Services → Repositories → Core (DB, Qdrant, Embedder)
"""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.embedder import Embedder, get_embedder
from app.core.exceptions import AuthenticationError, InvalidTokenError, TokenExpiredError
from app.core.qdrant_client import AsyncQdrantClient, get_qdrant_client
from app.core.security import extract_user_id
from app.models.user import User
from app.repositories.chat_repo import ChatRepository
from app.repositories.memory_repo import MemoryRepository
from app.repositories.personality_repo import PersonalityRepository
from app.repositories.user_repo import UserRepository
from app.services.ai_service import AIService
from app.services.auth_service import AuthService
from app.services.chat_service import ChatService
from app.services.memory_service import MemoryService
from app.services.personality_service import PersonalityService
from app.services.prompt_builder import PromptBuilder

# ── HTTP Bearer ───────────────────────────────────────────────────────────────

_bearer = HTTPBearer()


# ── Database session ──────────────────────────────────────────────────────────

DbSession = Annotated[AsyncSession, Depends(get_db_session)]


# ── Repositories ─────────────────────────────────────────────────────────────

def get_user_repo(session: DbSession) -> UserRepository:
    return UserRepository(session)


def get_personality_repo(session: DbSession) -> PersonalityRepository:
    return PersonalityRepository(session)


def get_chat_repo(session: DbSession) -> ChatRepository:
    return ChatRepository(session)


def get_memory_repo(
    client: Annotated[AsyncQdrantClient, Depends(get_qdrant_client)],
    embedder: Annotated[Embedder, Depends(get_embedder)],
) -> MemoryRepository:
    return MemoryRepository(client=client, embedder=embedder)


# ── Services ──────────────────────────────────────────────────────────────────

def get_ai_service() -> AIService:
    return AIService()


def get_prompt_builder() -> PromptBuilder:
    return PromptBuilder()


def get_auth_service(
    user_repo: Annotated[UserRepository, Depends(get_user_repo)],
) -> AuthService:
    return AuthService(user_repo)


def get_memory_service(
    memory_repo: Annotated[MemoryRepository, Depends(get_memory_repo)],
    ai_service: Annotated[AIService, Depends(get_ai_service)],
) -> MemoryService:
    return MemoryService(memory_repo=memory_repo, ai_service=ai_service)


def get_personality_service(
    personality_repo: Annotated[PersonalityRepository, Depends(get_personality_repo)],
    chat_repo: Annotated[ChatRepository, Depends(get_chat_repo)],
    ai_service: Annotated[AIService, Depends(get_ai_service)],
) -> PersonalityService:
    return PersonalityService(
        personality_repo=personality_repo,
        chat_repo=chat_repo,
        ai_service=ai_service,
    )


def get_chat_service(
    chat_repo: Annotated[ChatRepository, Depends(get_chat_repo)],
    personality_repo: Annotated[PersonalityRepository, Depends(get_personality_repo)],
    memory_service: Annotated[MemoryService, Depends(get_memory_service)],
    personality_service: Annotated[PersonalityService, Depends(get_personality_service)],
    ai_service: Annotated[AIService, Depends(get_ai_service)],
    prompt_builder: Annotated[PromptBuilder, Depends(get_prompt_builder)],
) -> ChatService:
    return ChatService(
        chat_repo=chat_repo,
        personality_repo=personality_repo,
        memory_service=memory_service,
        personality_service=personality_service,
        ai_service=ai_service,
        prompt_builder=prompt_builder,
    )


# ── Current User ─────────────────────────────────────────────────────────────

async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
    user_repo: Annotated[UserRepository, Depends(get_user_repo)],
) -> User:
    """
    Validate JWT, extract user_id, fetch User from DB.
    Raises 401 on any auth failure.
    """
    try:
        user_id = extract_user_id(credentials.credentials)
    except (TokenExpiredError, InvalidTokenError) as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=e.message)

    import uuid
    user = await user_repo.get_by_id(uuid.UUID(user_id))
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
