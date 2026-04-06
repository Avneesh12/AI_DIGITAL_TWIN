"""
app/core/qdrant_client.py
─────────────────────────
Qdrant async client singleton + collection bootstrap.
Collection uses cosine distance with 384-dim vectors (all-MiniLM-L6-v2).
"""
from __future__ import annotations

from functools import lru_cache

from loguru import logger
from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PayloadSchemaType,
    VectorParams,
)

from app.config import get_settings
from app.core.exceptions import VectorStoreError

settings = get_settings()

COLLECTION_NAME = settings.QDRANT_COLLECTION


@lru_cache(maxsize=1)
def get_qdrant_client() -> AsyncQdrantClient:
    """Cached Qdrant async client singleton."""
    kwargs: dict = {
        "host": settings.QDRANT_HOST,
        "port": settings.QDRANT_PORT,
    }
    if settings.QDRANT_API_KEY:
        kwargs["api_key"] = settings.QDRANT_API_KEY
        kwargs["https"] = True
    return AsyncQdrantClient(**kwargs)


async def ensure_collection_exists(client: AsyncQdrantClient) -> None:
    """
    Idempotent collection bootstrap.
    Creates the 'memories' collection if it doesn't exist yet.
    Also creates a payload index on 'user_id' for efficient per-user filtering.
    """
    try:
        existing = await client.get_collections()
        names = [c.name for c in existing.collections]

        if COLLECTION_NAME not in names:
            logger.info("Creating Qdrant collection", collection=COLLECTION_NAME)
            await client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(
                    size=settings.EMBEDDING_DIMENSION,
                    distance=Distance.COSINE,
                ),
            )

            # Index user_id for fast per-user filtering
            await client.create_payload_index(
                collection_name=COLLECTION_NAME,
                field_name="user_id",
                field_schema=PayloadSchemaType.KEYWORD,
            )
            logger.info("Qdrant collection created", collection=COLLECTION_NAME)
        else:
            logger.info("Qdrant collection already exists", collection=COLLECTION_NAME)
    except Exception as e:
        raise VectorStoreError(detail=f"Collection bootstrap failed: {e}") from e


def build_user_filter(user_id: str) -> Filter:
    """Build a Qdrant filter that restricts results to a single user."""
    return Filter(
        must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))]
    )
