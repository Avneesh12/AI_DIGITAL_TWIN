"""app/api/v1/router.py — Aggregates all v1 sub-routers."""
from fastapi import APIRouter

from app.api.v1 import auth, chat, memory, personality

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router)
api_router.include_router(chat.router)
api_router.include_router(personality.router)
api_router.include_router(memory.router)
