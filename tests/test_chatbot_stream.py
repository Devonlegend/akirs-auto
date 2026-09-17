"""Tests for the chatbot LLM streaming backend (no heavy torch imports)."""

from __future__ import annotations

import json

import pytest

from chatbot.llm.ollama_backend import OllamaBackend


class _FakeClient:
    """Mimics the subset of httpx.AsyncClient used by generate_stream."""

    def __init__(self, frames: list[dict]) -> None:
        self._frames = frames
        self._payload = None

    async def request(self, method, url, **kwargs):
        self._payload = kwargs.get("json")
        return _FakeResponse(self._frames)


class _FakeResponse:
    def __init__(self, frames: list[dict]) -> None:
        self._frames = frames

    def raise_for_status(self) -> None:
        return None

    async def aiter_lines(self):
        for frame in self._frames:
            yield json.dumps(frame)


@pytest.mark.asyncio
async def test_generate_stream_yields_deltas_and_final():
    frames = [
        {"message": {"content": "Hello"}, "done": False},
        {"message": {"content": " world"}, "done": True},
    ]
    backend = OllamaBackend()
    backend._client = _FakeClient(frames)

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


@pytest.mark.asyncio
async def test_generate_stream_sends_stream_tuning():
    from chatbot.config import settings

    backend = OllamaBackend()
    fake = _FakeClient([{"message": {"content": ""}, "done": True}])
    backend._client = fake

    async for _ in backend.generate_stream("sys", "ctx", "hi", max_tokens=50):
        pass

    payload = fake._payload
    assert payload["stream"] is True
    assert payload["keep_alive"] == settings.ollama_keep_alive
    assert payload["options"]["num_predict"] == 50
    assert payload["options"]["num_ctx"] == settings.ollama_num_ctx

