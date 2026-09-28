"""llama.cpp backend — calls llama-server's OpenAI-compatible HTTP API.

llama-server is a single-binary (or container) CPU inference server for GGUF
models.  It exposes ``/v1/chat/completions`` (OpenAI-compatible, streaming via
SSE), ``/v1/models``, and ``/health``.  The model is preloaded when the server
starts, so there is no pull/warm-up step on the client side — unlike Ollama,
this backend has no ``ensure_ready``.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import override

import httpx

from chatbot.config import settings
from chatbot.llm.base import LLMBackend, LLMResponse

logger = logging.getLogger(__name__)

_CHAT_COMPLETIONS_ENDPOINT = "/v1/chat/completions"
_MODELS_ENDPOINT = "/v1/models"
_HEALTH_ENDPOINT = "/health"


class LlamaCppBackend(LLMBackend):
    """Calls llama.cpp ``llama-server`` (OpenAI-compatible chat API).

    Usage::

        backend = LlamaCppBackend()
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
        *,
        api_key: str | None = None,
        max_retries: int = 2,
        retry_backoff: float = 0.5,
    ) -> None:
        self._model = model or settings.llamacpp_model
        self._base_url = (base_url or settings.llamacpp_base_url).rstrip("/")
        timeout_val = timeout if timeout is not None else settings.llm_timeout_seconds
        key = api_key if api_key is not None else settings.llamacpp_api_key
        self._max_retries = max_retries
        self._retry_backoff = retry_backoff
        headers = {"Authorization": f"Bearer {key}"} if key else {}
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_val),
            headers=headers,
        )

    async def _request_with_retry(
        self, method: str, url: str, **kwargs: object
    ) -> httpx.Response:
        """Issue an HTTP request, retrying only on transient transport/timeout errors.

        HTTP status errors (4xx/5xx) are NOT retried — they surface immediately.
        """
        attempt = 0
        while True:
            try:
                resp = await self._client.request(method, url, **kwargs)
                resp.raise_for_status()
                return resp
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                if attempt >= self._max_retries:
                    logger.error(
                        "llama.cpp request %s %s failed after %d attempts: %s",
                        method,
                        url,
                        attempt + 1,
                        exc,
                    )
                    raise
                delay = self._retry_backoff * (2**attempt)
                logger.warning(
                    "llama.cpp request %s %s failed (%s) — retrying in %.1fs.",
                    method,
                    url,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)
                attempt += 1

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _messages(system_prompt: str, context: str, question: str) -> list[dict]:
        """Build the OpenAI-style message list (same shape as OllamaBackend)."""
        messages: list[dict] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        user_content = f"Context:\n{context}\n\nQuestion: {question}"
        messages.append({"role": "user", "content": user_content})
        return messages

    def _payload(
        self,
        messages: list[dict],
        *,
        temperature: float | None,
        max_tokens: int | None,
        stream: bool,
    ) -> dict:
        temp = temperature if temperature is not None else settings.llm_temperature
        max_tok = max_tokens if max_tokens is not None else settings.llm_max_tokens
        return {
            "model": self._model,
            "messages": messages,
            "stream": stream,
            "temperature": temp,
            "max_tokens": max_tok,
        }

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
        payload = self._payload(
            self._messages(system_prompt, context, question),
            temperature=temperature,
            max_tokens=max_tokens,
            stream=False,
        )

        logger.debug("Calling llama.cpp model=%s ...", self._model)

        try:
            resp = await self._request_with_retry(
                "POST",
                f"{self._base_url}{_CHAT_COMPLETIONS_ENDPOINT}",
                json=payload,
            )
            data = resp.json()
        except httpx.HTTPError as exc:
            logger.error("llama.cpp API call failed: %s", exc)
            raise

        content = (
            (data.get("choices") or [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )
        total_tokens = (data.get("usage") or {}).get("total_tokens", 0)

        logger.debug("llama.cpp response: %d tokens.", total_tokens)

        return LLMResponse(
            content=content,
            model=data.get("model", self._model),
            total_tokens=total_tokens,
            metadata={
                "prompt_tokens": (data.get("usage") or {}).get("prompt_tokens", 0),
                "completion_tokens": (data.get("usage") or {}).get(
                    "completion_tokens", 0
                ),
            },
        )

    async def generate_stream(
        self,
        system_prompt: str,
        context: str,
        question: str,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ):
        """Stream the answer token-by-token (OpenAI SSE, ``stream: true``).

        Yields ``(delta, final_metadata)`` pairs — the same contract as
        ``OllamaBackend.generate_stream`` and what ``pipeline.ask_stream``
        consumes.  llama.cpp streams ``data: {...}`` SSE frames and terminates
        with ``data: [DONE]``.
        """
        payload = self._payload(
            self._messages(system_prompt, context, question),
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )

        logger.debug("Streaming llama.cpp model=%s ...", self._model)
        resp = await self._request_with_retry(
            "POST",
            f"{self._base_url}{_CHAT_COMPLETIONS_ENDPOINT}",
            json=payload,
        )
        async for line in resp.aiter_lines():
            line = line.strip()
            if not line or not line.startswith("data:"):
                continue
            data = line[len("data:"):].strip()
            if data == "[DONE]":
                yield "", True
                return
            try:
                evt = json.loads(data)
            except ValueError:
                continue
            if evt.get("error"):
                raise RuntimeError(f"llama.cpp stream error: {evt['error']}")
            delta = (
                (evt.get("choices") or [{}])[0]
                .get("delta", {})
                .get("content", "")
            )
            if delta:
                yield delta, False
        # Stream ended without an explicit [DONE] — treat as final.
        yield "", True

    @override
    async def health_check(self) -> bool:
        """Check llama-server reachability via ``/health``, falling back to
        ``/v1/models`` (older builds only expose the OpenAI endpoints)."""
        try:
            resp = await self._client.get(f"{self._base_url}{_HEALTH_ENDPOINT}")
            if resp.status_code == 200:
                return True
        except httpx.HTTPError:
            pass
        try:
            resp = await self._request_with_retry(
                "GET",
                f"{self._base_url}{_MODELS_ENDPOINT}",
            )
            data = resp.json()
            return isinstance(data, dict) and bool(data.get("data"))
        except httpx.HTTPError as exc:
            logger.error("llama.cpp health check failed: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> "LlamaCppBackend":
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()
