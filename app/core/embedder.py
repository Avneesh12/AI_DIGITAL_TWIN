"""
app/core/embedder.py
────────────────────
Calls the HuggingFace Inference API for embeddings instead of loading
the model locally. Zero RAM overhead, no torch/sentence-transformers
dependencies needed at runtime.

API used:
  POST https://api-inference.huggingface.co/models/sentence-transformers/all-MiniLM-L6-v2

The model outputs 384-dimensional cosine-normalised vectors — identical
shape to the local model, so Qdrant collection config is unchanged.

Cold-start note: HF free tier "wakes up" the model on the first request
after inactivity. The first call may take 20–30 s. Subsequent calls are
fast (~200–400 ms). We handle this with automatic retry + backoff.
"""
from __future__ import annotations

import asyncio
import hashlib
from functools import lru_cache

import httpx
from loguru import logger

from app.config import get_settings
from app.core.exceptions import EmbeddingError

settings = get_settings()


MODEL = "sentence-transformers/all-MiniLM-L6-v2"  # ✅ Reliable free model
_HF_API_URL = f"https://router.huggingface.co/hf-inference/models/{MODEL}/pipeline/feature-extraction"

_DIMENSION = 384
_MAX_RETRIES = 5          # model cold-start can take several retries
_RETRY_DELAY = 5.0        # seconds between retries when model is loading


class Embedder:
    """
    Async HuggingFace Inference API client for sentence embeddings.

    Usage:
        embedder = get_embedder()
        vector = await embedder.embed("some text")
    """

    def __init__(self, hf_token: str | None) -> None:
        self._headers: dict[str, str] = {"Content-Type": "application/json"}
        if hf_token:
            self._headers["Authorization"] = f"Bearer {hf_token}"
        else:
            logger.warning(
                "HF_TOKEN not set — requests will be rate-limited to ~30 req/hour. "
                "Add HF_TOKEN to .env for higher limits."
            )

    @property
    def dimension(self) -> int:
        return _DIMENSION

    async def embed(self, text: str) -> list[float]:
        """
        Embed a single string. Retries automatically while the model is
        loading (HF returns HTTP 503 with 'loading' in the body).
        """
        return await self._call_api(text)

    async def embed_pair(self, text_a: str, text_b: str) -> list[float]:
        """
        Embed the concatenation of two strings separated by [SEP].
        Used when storing a memory (user_message + assistant_response).
        """
        combined = f"{text_a} [SEP] {text_b}"
        return await self.embed(combined)

    async def _call_api(self, text: str) -> list[float]:
        payload = {
            "inputs": text,
            "options": {"wait_for_model": True},   # tells HF to block until ready
        }

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(
                        _HF_API_URL,
                        headers=self._headers,
                        json=payload,
                    )

                # Model still loading — wait and retry
                if response.status_code == 503:
                    body = response.json()
                    wait = float(body.get("estimated_time", _RETRY_DELAY))
                    logger.info(
                        "HF model loading, retrying",
                        attempt=attempt,
                        wait_seconds=wait,
                    )
                    await asyncio.sleep(min(wait, 30.0))
                    continue

                if response.status_code == 429:
                    raise EmbeddingError(
                        message="HuggingFace rate limit hit. Add HF_TOKEN to .env for higher limits.",
                        detail=response.text,
                    )

                response.raise_for_status()
                data = response.json()
                return self._parse_response(data, text)

            except EmbeddingError:
                raise
            except httpx.TimeoutException:
                if attempt == _MAX_RETRIES:
                    raise EmbeddingError(message="HuggingFace API timed out after retries")
                await asyncio.sleep(_RETRY_DELAY)
            except httpx.HTTPStatusError as e:
                raise EmbeddingError(
                    message=f"HuggingFace API error: {e.response.status_code}",
                    detail=e.response.text[:300],
                ) from e
            except Exception as e:
                raise EmbeddingError(detail=str(e)) from e

        raise EmbeddingError(message="HuggingFace model failed to load after max retries")

    @staticmethod
    def _parse_response(data: object, original_text: str) -> list[float]:
        """
        HF Inference API returns one of:
          - list[float]               (single embedding, older API versions)
          - list[list[float]]         (batch of embeddings — we sent one text)
          - list[list[list[float]]]   (token-level embeddings for some models)

        We always want a flat list[float] of length 384.
        """
        # Unwrap nested lists until we reach the flat vector
        result = data
        while isinstance(result, list) and isinstance(result[0], list):
            result = result[0]

        if not isinstance(result, list) or not isinstance(result[0], float):
            raise EmbeddingError(
                detail=f"Unexpected HF response shape: {type(data)}"
            )

        if len(result) != _DIMENSION:
            raise EmbeddingError(
                detail=f"Expected {_DIMENSION}-dim vector, got {len(result)}"
            )

        return result


@lru_cache(maxsize=1)
def get_embedder() -> Embedder:
    """Cached singleton — created once, reused for every request."""
    return Embedder(hf_token=settings.HF_TOKEN)


def deterministic_point_id(chat_id: str) -> str:
    """
    Deterministic Qdrant point ID derived from chat_id.
    Guarantees idempotent upserts — same chat always maps to the same point.
    """
    return hashlib.sha256(chat_id.encode()).hexdigest()[:32]