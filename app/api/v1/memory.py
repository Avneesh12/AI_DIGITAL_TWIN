"""app/api/v1/memory.py — Memory list + delete."""
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from app.dependencies import CurrentUser, get_memory_service
from app.schemas.memory import MemoryEntry, MemorySearchResult
from app.services.memory_service import MemoryService

router = APIRouter(prefix="/memory", tags=["Memory"])


@router.get("", response_model=list[MemoryEntry])
async def list_memories(
    current_user: CurrentUser,
    svc: Annotated[MemoryService, Depends(get_memory_service)],
    limit: int = Query(default=50, ge=1, le=200),
) -> list[MemoryEntry]:
    """List all stored memories for the authenticated user."""
    memories = await svc.list_memories(str(current_user.id), limit=limit)
    return [
        MemoryEntry(
            point_id=str(m.get("point_id", "")),
            user_message=m.get("user_message", ""),
            assistant_response=m.get("assistant_response", ""),
            topic_tags=m.get("topic_tags", []),
            emotional_tone=m.get("emotional_tone"),
            importance_score=m.get("importance_score", 0.5),
            created_at=m.get("created_at", ""),
        )
        for m in memories
    ]


@router.delete("/{point_id}", status_code=204)
async def delete_memory(
    point_id: str,
    current_user: CurrentUser,
    svc: Annotated[MemoryService, Depends(get_memory_service)],
) -> None:
    """Delete a specific memory point."""
    await svc.delete_memory(point_id)


@router.delete("", status_code=204)
async def delete_all_memories(
    current_user: CurrentUser,
    svc: Annotated[MemoryService, Depends(get_memory_service)],
) -> None:
    """Delete ALL memories for the authenticated user. Irreversible."""
    await svc.delete_all(str(current_user.id))
