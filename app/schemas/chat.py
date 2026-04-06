"""app/schemas/chat.py — Chat request/response schemas."""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    session_id: uuid.UUID | None = None  # Auto-generated if not provided


class ChatResponse(BaseModel):
    response: str
    session_id: str
    chat_id: str
    memories_used: int       # How many memories were retrieved
    tokens_used: int


class ChatHistoryItem(BaseModel):
    id: str
    role: str                # 'user' | 'assistant'
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}
