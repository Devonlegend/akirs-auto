"""Tests for the llama.cpp (OpenAI-compatible) LLM backend — no live server."""

from __future__ import annotations

import json

import pytest

from chatbot.llm.llamacpp_backend import LlamaCppBackend


class _FakeClient:
    """Mimics the subset of httpx.AsyncClient used by the backend."""

    def __init__(self, response: "_FakeResponse") -> None:
        self._response = response
        self.last_payload = None
        self.last_url = None

    async def request(self, method, url, **kwargs):
        self.last_payload = kwargs.get("json")
        self.last_url = url
        return self._response


class _FakeResponse:
    def __init__(self, *, json_data: dict | None = None, lines: list[str] | None = None) -> None:
        self._json_data = json_data or {}
        self._lines = lines or []

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self._json_data

    async def aiter_lines(self):
        for line in self._lines:
            yield line


# ------------------------------------------------------------------
# generate()
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_maps_openai_response():
    fake_resp = _FakeResponse(
        json_data={
            "model": "gemma-3-1b",
            "choices": [{"message": {"content": "  Jane Doe was born in Lagos.  "}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 7, "total_tokens": 17},
        }
    )
    backend = LlamaCppBackend()
    backend._client = _FakeClient(fake_resp)

    resp = await backend.generate(
        system_prompt="You are helpful.",
        context="Jane Doe was born in Lagos.",
        question="Where was Jane Doe born?",
    )

    assert resp.content == "Jane Doe was born in Lagos."
    assert resp.model == "gemma-3-1b"
    assert resp.total_tokens == 17
    assert resp.metadata["prompt_tokens"] == 10
    assert resp.metadata["completion_tokens"] == 7

    payload = backend._client.last_payload
    assert payload["stream"] is False
    assert payload["messages"][0] == {"role": "system", "content": "You are helpful."}
    assert payload["messages"][1]["role"] == "user"
    assert "Jane Doe was born in Lagos." in payload["messages"][1]["content"]
    assert "Where was Jane Doe born?" in payload["messages"][1]["content"]


@pytest.mark.asyncio
async def test_generate_respects_overrides():
    fake_resp = _FakeResponse(json_data={"choices": [{"message": {"content": "ok"}}]})
    backend = LlamaCppBackend()
    backend._client = _FakeClient(fake_resp)

    await backend.generate("sys", "ctx", "q", temperature=0.9, max_tokens=42)

    payload = backend._client.last_payload
    assert payload["temperature"] == 0.9
    assert payload["max_tokens"] == 42


# ------------------------------------------------------------------
# generate_stream()
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_stream_yields_deltas_and_final():
    frames = [
        {"choices": [{"delta": {"content": "Hello"}}]},
        {"choices": [{"delta": {"content": " world"}}]},
    ]
    lines = [f"data: {json.dumps(f)}" for f in frames] + ["data: [DONE]"]
    backend = LlamaCppBackend()
    backend._client = _FakeClient(_FakeResponse(lines=lines))

    deltas: list[str] = []
    saw_final = False
    async for delta, final in backend.generate_stream(
        system_prompt="sys", context="ctx", question="hi"
    ):
        if delta:
            deltas.append(delta)
        if final:
            saw_final = True

    assert "".join(deltas) == "Hello world"
    assert saw_final is True
    assert backend._client.last_payload["stream"] is True


@pytest.mark.asyncio
async def test_generate_stream_final_without_done_frame():
    # Server closed the connection without sending [DONE].
    lines = [f"data: {json.dumps({'choices': [{'delta': {'content': 'Hi'}}]})}"]
    backend = LlamaCppBackend()
    backend._client = _FakeClient(_FakeResponse(lines=lines))

    events = [
        (delta, final)
        async for delta, final in backend.generate_stream("s", "c", "q")
    ]
    assert ("Hi", False) in events
    assert events[-1] == ("", True)


@pytest.mark.asyncio
async def test_generate_stream_raises_on_error_frame():
    lines = [f"data: {json.dumps({'error': {'message': 'boom'}})}"]
    backend = LlamaCppBackend()
    backend._client = _FakeClient(_FakeResponse(lines=lines))

    with pytest.raises(RuntimeError, match="llama.cpp stream error"):
        async for _ in backend.generate_stream("s", "c", "q"):
            pass


# ------------------------------------------------------------------
# health_check()
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_check_true_via_health_endpoint():
    class _Client:
        async def get(self, url, **kwargs):
            resp = _FakeResponse()
            resp.status_code = 200
            return resp

    backend = LlamaCppBackend()
    backend._client = _Client()
    assert await backend.health_check() is True


@pytest.mark.asyncio
async def test_health_check_true_via_models_fallback():
    class _Client:
        async def get(self, url, **kwargs):
            resp = _FakeResponse()
            resp.status_code = 404
            return resp

        async def request(self, method, url, **kwargs):
            return _FakeResponse(json_data={"data": [{"id": "gemma-3-1b"}]})

    backend = LlamaCppBackend()
    backend._client = _Client()
    assert await backend.health_check() is True


@pytest.mark.asyncio
async def test_health_check_false_when_unreachable():
    import httpx

    class _DownClient:
        async def get(self, url, **kwargs):
            raise httpx.ConnectError("refused")

        async def request(self, method, url, **kwargs):
            raise httpx.ConnectError("refused")

    backend = LlamaCppBackend(max_retries=0)
    backend._client = _DownClient()
    assert await backend.health_check() is False
