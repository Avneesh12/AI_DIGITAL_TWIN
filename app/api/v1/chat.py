"""
app/api/v1/chat.py
──────────────────
The main /chat endpoint — the entry point to the full AI pipeline.
Also exposes /chat/history for session review.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.dependencies import CurrentUser, get_chat_service
from app.schemas.chat import ChatHistoryItem, ChatRequest, ChatResponse
from app.services.chat_service import ChatService

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: CurrentUser,
    chat_svc: Annotated[ChatService, Depends(get_chat_service)],
) -> ChatResponse:
    """
    Send a message to your AI Digital Twin.

    Pipeline:
    1. Load personality profile
    2. Retrieve relevant memories (RAG)
    3. Build system prompt
    4. Generate response via Grok
    5. Persist exchange + store memory vector
    """
    return await chat_svc.handle(user=current_user, request=request)


@router.get("/history", response_model=list[ChatHistoryItem])
async def get_history(
    current_user: CurrentUser,
    chat_svc: Annotated[ChatService, Depends(get_chat_service)],
    limit: int = Query(default=20, ge=1, le=100),
) -> list[ChatHistoryItem]:
    """Return recent chat history for the authenticated user."""
    chats = await chat_svc._chat_repo.get_recent_chats(current_user.id, limit=limit)
    return [
        ChatHistoryItem(
            id=str(c.id),
            role=c.role,
            content=c.content,
            created_at=c.created_at,
        )
        for c in chats
    ]
