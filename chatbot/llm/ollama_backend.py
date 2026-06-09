"""Ollama backend — calls the local Ollama HTTP API for Phi-4-mini."""

from __future__ import annotations

import logging
from typing import override

import httpx

from chatbot.config import settings
from chatbot.llm.base import LLMBackend, LLMResponse

logger = logging.getLogger(__name__)

_OLLAMA_CHAT_ENDPOINT = "/api/chat"
_OLLAMA_TAGS_ENDPOINT = "/api/tags"


class OllamaBackend(LLMBackend):
    """Calls Ollama's chat API with Phi-4-mini.

    Usage::

        backend = OllamaBackend()
        response = await backend.generate(
            system_prompt="You are a helpful assistant.",
            context="Jane Doe was born in Lagos.",
            question="Where was Jane Doe born?",
        )
        print(response.content)  # → "Jane Doe was born in Lagos."
    """

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self._model = model or settings.ollama_model
        self._base_url = (base_url or settings.ollama_base_url).rstrip("/")
        timeout_val = timeout if timeout is not None else settings.llm_timeout_seconds
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_val),
        )

    # ------------------------------------------------------------------
    # LLMBackend implementation
    # ------------------------------------------------------------------

    @override
    async def generate(
        self,
        system_prompt: str,
        context: str,
        question: str,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        temp = temperature if temperature is not None else settings.llm_temperature
        max_tok = max_tokens if max_tokens is not None else settings.llm_max_tokens

        messages: list[dict] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # Build user message with context + question.
        user_content = f"Context:\n{context}\n\nQuestion: {question}"
        messages.append({"role": "user", "content": user_content})

        payload = {
            "model": self._model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temp,
                "num_predict": max_tok,
            },
        }

        logger.debug("Calling Ollama model=%s ...", self._model)

        try:
            resp = await self._client.post(
                f"{self._base_url}{_OLLAMA_CHAT_ENDPOINT}",
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as exc:
            logger.error("Ollama API call failed: %s", exc)
            raise

        content = data.get("message", {}).get("content", "").strip()
        eval_count = data.get("eval_count", 0)

        logger.debug("Ollama response: %d tokens.", eval_count)

        return LLMResponse(
            content=content,
            model=data.get("model", self._model),
            total_tokens=eval_count,
            metadata={
                "total_duration": data.get("total_duration", 0),
                "load_duration": data.get("load_duration", 0),
                "prompt_eval_count": data.get("prompt_eval_count", 0),
            },
        )

    @override
    @override
    async def health_check(self) -> bool:
        """Check if Ollama is reachable and the model is available."""
        try:
            resp = await self._client.get(
                f"{self._base_url}{_OLLAMA_TAGS_ENDPOINT}",
            )
            resp.raise_for_status()
            data = resp.json()
            if not isinstance(data, dict):
                return False
            models_list = data.get("models")
            if not isinstance(models_list, list):
                return False
            models = [m.get("name", "") for m in models_list if isinstance(m, dict)]
            # Check if our model (or a prefix match) is available.
            available = any(
                m == self._model or m.startswith(f"{self._model}:")
                for m in models
            )
                logger.warning(
                    "Model '%s' not found in Ollama. Available: %s",
                    self._model,
                    models,
                )
            return available
        except httpx.HTTPError as exc:
            logger.error("Ollama health check failed: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> "OllamaBackend":
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()
