"""
app/services/ai_service.py
──────────────────────────
Async wrapper around the Grok (xAI) API.
Uses httpx for async HTTP — no vendor SDK lock-in.
"""
from __future__ import annotations

import re

import httpx
from loguru import logger

from app.config import get_settings
from app.core.exceptions import LLMServiceError

settings = get_settings()

# Phrases that break the "you ARE the user" illusion — strip them
_AI_PHRASES = re.compile(
    r"\b(as an ai|i'm an ai|i am an ai|as a language model|"
    r"i don't have personal|i cannot have opinions|"
    r"i'm just an ai|i don't actually)\b",
    re.IGNORECASE,
)


class AIService:
    """
    Wraps the Grok /v1/chat/completions endpoint.
    Handles request construction, error handling, and post-processing.
    """

    def __init__(self) -> None:
        self._base_url = settings.GROK_API_BASE
        self._api_key = settings.GROK_API_KEY
        self._model = settings.GROK_MODEL
        self._headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    async def chat(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> tuple[str, int]:
        """
        Send messages to Grok and return (response_text, tokens_used).
        Post-processes the response to remove AI-sounding phrases.
        """
        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers=self._headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException:
            raise LLMServiceError(message="Grok API request timed out")
        except httpx.HTTPStatusError as e:
            logger.error("Grok API HTTP error", status=e.response.status_code, body=e.response.text)
            raise LLMServiceError(
                message=f"Grok API returned {e.response.status_code}",
                detail=e.response.text[:500],
            )
        except Exception as e:
            raise LLMServiceError(detail=str(e)) from e

        try:
            content = data["choices"][0]["message"]["content"]
            tokens = data.get("usage", {}).get("total_tokens", 0)
        except (KeyError, IndexError) as e:
            raise LLMServiceError(detail=f"Unexpected response structure: {e}") from e

        return self._post_process(content), tokens

    async def json_completion(
        self,
        prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 512,
    ) -> str:
        """
        Request a structured JSON response from Grok.
        Lower temperature for deterministic classification tasks.
        """
        messages = [
            {"role": "system", "content": "You are a precise JSON generator. Output only valid JSON, no markdown."},
            {"role": "user", "content": prompt},
        ]
        text, _ = await self.chat(messages, temperature=temperature, max_tokens=max_tokens)
        return text

    @staticmethod
    def _post_process(text: str) -> str:
        """
        Strip phrases that break the digital twin illusion.
        This is a lightweight guardrail; personality prompting does the heavy lifting.
        """
        cleaned = _AI_PHRASES.sub("", text)
        # Collapse any double spaces created by removal
        cleaned = re.sub(r"  +", " ", cleaned).strip()
        return cleaned
