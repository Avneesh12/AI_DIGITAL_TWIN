"""
app/core/embedder.py
────────────────────
Singleton wrapper around sentence-transformers embedding model.
Loaded once at startup; subsequent calls reuse the cached instance.
Thread-safe for async use (CPU-bound work is run in threadpool via anyio).
"""
from __future__ import annotations

import hashlib
from functools import lru_cache

import anyio
from loguru import logger
from sentence_transformers import SentenceTransformer

from app.config import get_settings
from app.core.exceptions import EmbeddingError

settings = get_settings()


class Embedder:
    """
    Wraps SentenceTransformer with async-friendly interface.

    Usage:
        embedder = get_embedder()
        vector = await embedder.embed("some text")
    """

    def __init__(self, model_name: str) -> None:
        logger.info("Loading embedding model", model=model_name)
        try:
            self._model = SentenceTransformer(model_name)
            self._dim = self._model.get_sentence_embedding_dimension()
            logger.info("Embedding model loaded", dimension=self._dim)
        except Exception as e:
            raise EmbeddingError(detail=str(e)) from e

    @property
    def dimension(self) -> int:
        return self._dim  # type: ignore[return-value]

    def _encode_sync(self, text: str) -> list[float]:
        """CPU-bound; called from threadpool."""
        vector = self._model.encode(text, normalize_embeddings=True)
        return vector.tolist()

    async def embed(self, text: str) -> list[float]:
        """
        Async wrapper: runs encoding in a threadpool so it doesn't
        block the event loop.
        """
        try:
            return await anyio.to_thread.run_sync(self._encode_sync, text)
        except Exception as e:
            raise EmbeddingError(detail=str(e)) from e

    async def embed_pair(self, text_a: str, text_b: str) -> list[float]:
        """
        Embed the concatenation of two texts (user_message + assistant_response).
        Used when storing a memory after a chat exchange.
        """
        combined = f"{text_a} [SEP] {text_b}"
        return await self.embed(combined)


@lru_cache(maxsize=1)
def get_embedder() -> Embedder:
    """Cached singleton — safe to inject as a FastAPI dependency."""
    return Embedder(settings.EMBEDDING_MODEL)


def deterministic_point_id(chat_id: str) -> str:
    """
    Generate a deterministic Qdrant point ID from a chat_id UUID.
    Ensures idempotent upserts: the same chat always maps to the same vector point.
    Returns a hex string (Qdrant accepts string IDs).
    """
    return hashlib.sha256(chat_id.encode()).hexdigest()[:32]
