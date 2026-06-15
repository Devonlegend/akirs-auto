"""Tests for the Ollama backend — model detection, health check, retry helper.

Uses httpx.MockTransport so no real Ollama server is contacted.
"""

from __future__ import annotations

import httpx
import pytest

from src.chatbot.llm.ollama_backend import OllamaBackend


def _backend_with_handler(handler, **kwargs) -> OllamaBackend:
    backend = OllamaBackend(model="phi4-mini", base_url="http://test", **kwargs)
    backend._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return backend


def _tags_response(model_names: list[str]) -> httpx.Response:
    return httpx.Response(200, json={"models": [{"name": n} for n in model_names]})


async def test_model_present_exact_match():
    backend = _backend_with_handler(lambda req: _tags_response(["phi4-mini", "llama3"]))
    assert await backend._model_present() is True
    await backend.close()


async def test_model_present_prefix_match():
    backend = _backend_with_handler(lambda req: _tags_response(["phi4-mini:latest"]))
    assert await backend._model_present() is True
    await backend.close()


async def test_model_present_absent():
    backend = _backend_with_handler(lambda req: _tags_response(["llama3", "mistral"]))
    assert await backend._model_present() is False
    await backend.close()


async def test_health_check_true_when_model_present():
    backend = _backend_with_handler(lambda req: _tags_response(["phi4-mini"]))
    assert await backend.health_check() is True
    await backend.close()


async def test_health_check_false_when_model_absent():
    backend = _backend_with_handler(lambda req: _tags_response(["other"]))
    assert await backend.health_check() is False
    await backend.close()


async def test_health_check_false_on_transport_error():
    def handler(req):
        raise httpx.ConnectError("refused", request=req)

    backend = _backend_with_handler(handler, max_retries=0)
    assert await backend.health_check() is False
    await backend.close()


async def test_request_retries_transient_then_succeeds():
    calls = {"n": 0}

    def handler(req):
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ConnectError("transient", request=req)
        return _tags_response(["phi4-mini"])

    backend = _backend_with_handler(handler, max_retries=2, retry_backoff=0.0)
    resp = await backend._request_with_retry("GET", "http://test/api/tags")
    assert resp.status_code == 200
    assert calls["n"] == 2  # failed once, retried once
    await backend.close()


async def test_request_does_not_retry_http_status_error():
    calls = {"n": 0}

    def handler(req):
        calls["n"] += 1
        return httpx.Response(500, text="boom")

    backend = _backend_with_handler(handler, max_retries=3, retry_backoff=0.0)
    with pytest.raises(httpx.HTTPStatusError):
        await backend._request_with_retry("GET", "http://test/api/tags")
    assert calls["n"] == 1  # status errors are not retried
    await backend.close()
