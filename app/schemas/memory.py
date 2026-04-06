"""app/schemas/memory.py — Memory entry schemas."""
from datetime import datetime

from pydantic import BaseModel


class MemoryEntry(BaseModel):
    point_id: str
    user_message: str
    assistant_response: str
    topic_tags: list[str]
    emotional_tone: str | None
    importance_score: float
    created_at: str


class MemorySearchResult(BaseModel):
    point_id: str
    score: float
    user_message: str
    assistant_response: str
    topic_tags: list[str]
    created_at: str
