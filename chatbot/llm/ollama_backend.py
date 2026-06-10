"""Ollama backend — calls the local Ollama HTTP API for Phi-4-mini."""

from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess
import sys
import time
from typing import override

import httpx

from chatbot.config import settings
from chatbot.llm.base import LLMBackend, LLMResponse

logger = logging.getLogger(__name__)

_OLLAMA_CHAT_ENDPOINT = "/api/chat"
_OLLAMA_TAGS_ENDPOINT = "/api/tags"
_OLLAMA_PULL_ENDPOINT = "/api/pull"


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
        *,
        max_retries: int = 2,
        retry_backoff: float = 0.5,
    ) -> None:
        self._model = model or settings.ollama_model
        self._base_url = (base_url or settings.ollama_base_url).rstrip("/")
        timeout_val = timeout if timeout is not None else settings.llm_timeout_seconds
        self._max_retries = max_retries
        self._retry_backoff = retry_backoff
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_val),
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
                        "Ollama request %s %s failed after %d attempts: %s",
                        method,
                        url,
                        attempt + 1,
                        exc,
                    )
                    raise
                delay = self._retry_backoff * (2**attempt)
                logger.warning(
                    "Ollama request %s %s failed (%s) — retrying in %.1fs.",
                    method,
                    url,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)
                attempt += 1

    # ------------------------------------------------------------------
    # Startup bootstrap
    # ------------------------------------------------------------------

    async def ensure_ready(self, *, pull_timeout: float = 600.0) -> None:
        """Ensure Ollama is running and the configured model is available.

        Steps:
        1. If the server is unreachable, try to start ``ollama serve`` locally.
        2. If the model is not present, pull it.
        3. Warm the model with a tiny generation so the first real query is fast.

        Raises:
            RuntimeError: if the server can't be reached/started or the model
            can't be pulled.
        """
        if not await self._server_up():
            await self._start_server()

        if not await self._model_present():
            logger.info("Model '%s' not found locally — pulling...", self._model)
            await self._pull_model(timeout=pull_timeout)

        await self._warm_up()
        logger.info("Ollama ready: model '%s' at %s.", self._model, self._base_url)

    async def _server_up(self) -> bool:
        try:
            resp = await self._client.get(f"{self._base_url}{_OLLAMA_TAGS_ENDPOINT}")
            resp.raise_for_status()
            return True
        except httpx.HTTPError:
            return False

    async def _start_server(self) -> None:
        """Launch ``ollama serve`` in the background and wait for it to come up."""
        exe = shutil.which("ollama")
        if exe is None:
            raise RuntimeError(
                "Ollama is not running and the 'ollama' binary was not found on PATH. "
                "Install it from https://ollama.com/download and try again."
            )

        logger.info("Starting Ollama server (%s serve)...", exe)
        creationflags = 0
        if sys.platform == "win32":
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            subprocess.Popen(
                [exe, "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                creationflags=creationflags,
            )
        except OSError as exc:
            raise RuntimeError(f"Failed to launch 'ollama serve': {exc}") from exc

        # Poll for readiness (up to ~30s).
        deadline = time.monotonic() + 30.0
        while time.monotonic() < deadline:
            if await self._server_up():
                return
            await asyncio.sleep(0.5)
        raise RuntimeError(
            "Started 'ollama serve' but the server did not become reachable at "
            f"{self._base_url} within 30s."
        )

    async def _model_present(self) -> bool:
        try:
            resp = await self._client.get(f"{self._base_url}{_OLLAMA_TAGS_ENDPOINT}")
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError:
            return False
        models = [
            m.get("name", "")
            for m in (data.get("models") or [])
            if isinstance(m, dict)
        ]
        return any(
            m == self._model or m.startswith(f"{self._model}:") for m in models
        )

    async def _pull_model(self, *, timeout: float) -> None:
        """Pull the model via the Ollama API, streaming progress to the log."""
        try:
            async with self._client.stream(
                "POST",
                f"{self._base_url}{_OLLAMA_PULL_ENDPOINT}",
                json={"model": self._model, "stream": True},
                timeout=httpx.Timeout(timeout),
            ) as resp:
                resp.raise_for_status()
                last_status = ""
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    import json

                    try:
                        evt = json.loads(line)
                    except ValueError:
                        continue
                    status = evt.get("status", "")
                    if status and status != last_status:
                        logger.info("Pulling '%s': %s", self._model, status)
                        last_status = status
                    if evt.get("error"):
                        raise RuntimeError(f"Ollama pull error: {evt['error']}")
        except httpx.HTTPError as exc:
            raise RuntimeError(
                f"Failed to pull model '{self._model}': {exc}"
            ) from exc

        if not await self._model_present():
            raise RuntimeError(
                f"Model '{self._model}' still not present after pull."
            )

    async def _warm_up(self) -> None:
        """Send a tiny request so the model is loaded into memory."""
        try:
            await self._client.post(
                f"{self._base_url}{_OLLAMA_CHAT_ENDPOINT}",
                json={
                    "model": self._model,
                    "messages": [{"role": "user", "content": "ok"}],
                    "stream": False,
                    "options": {"num_predict": 1},
                },
            )
        except httpx.HTTPError as exc:
            # Non-fatal — the model is present, warming just failed.
            logger.warning("Model warm-up failed (non-fatal): %s", exc)

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
            resp = await self._request_with_retry(
                "POST",
                f"{self._base_url}{_OLLAMA_CHAT_ENDPOINT}",
                json=payload,
            )
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
    async def health_check(self) -> bool:
        """Check if Ollama is reachable and the model is available."""
        try:
            resp = await self._request_with_retry(
                "GET",
                f"{self._base_url}{_OLLAMA_TAGS_ENDPOINT}",
            )
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
            if not available:
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
