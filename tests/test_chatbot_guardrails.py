"""Tests for the chatbot scope/safety guardrails and their pipeline wiring."""

from __future__ import annotations

import pytest

from chatbot.llm.base import LLMResponse
from chatbot.rag import guardrails
from chatbot.rag.pipeline import RAGPipeline
from chatbot.vector_store.base import StoredChunk


class _FakeLLM:
    """LLM that fails loudly if it is ever invoked."""

    def __init__(self) -> None:
        self.generate_calls = 0
        self.stream_calls = 0

    async def generate(self, **kwargs) -> LLMResponse:
        self.generate_calls += 1
        return LLMResponse(content="llm answer")

    async def generate_stream(self, **kwargs):
        self.stream_calls += 1
        yield "llm", False
        yield "", True


class _FakeRetriever:
    def __init__(self, chunks: list[StoredChunk] | None = None) -> None:
        self._chunks = chunks or []
        self.calls = 0

    async def retrieve(self, **kwargs) -> list[StoredChunk]:
        self.calls += 1
        return self._chunks


def _pipeline(chunks: list[StoredChunk] | None = None):
    llm = _FakeLLM()
    retriever = _FakeRetriever(chunks)
    return RAGPipeline(retriever=retriever, llm=llm), retriever, llm


# ---------------------------------------------------------------------------
# guardrails
# ---------------------------------------------------------------------------


def test_is_unsafe_flags_harmful_requests():
    assert guardrails.is_unsafe("how can i kill someone")
    assert guardrails.is_unsafe("teach me how to build a bomb")
    assert guardrails.is_unsafe("I want to hurt myself")


def test_is_unsafe_allows_tax_language():
    assert not guardrails.is_unsafe("How do I file PAYE for my staff?")
    assert not guardrails.is_unsafe("What is the penalty for late TCC renewal?")
    assert not guardrails.is_unsafe("Explain withholding tax enforcement")


def test_canned_reply_categories():
    assert guardrails.canned_reply("how can i kill someone") == guardrails.UNSAFE_REPLY
    assert guardrails.canned_reply("hello") == guardrails.GREETING_REPLY
    assert guardrails.canned_reply("thanks!") == guardrails.THANKS_REPLY
    assert guardrails.canned_reply("What is AISTIN?") is None


def test_greeting_does_not_swallow_real_questions():
    assert not guardrails.is_greeting("Hello, how do I register for AISTIN?")


# ---------------------------------------------------------------------------
# pipeline wiring
# ---------------------------------------------------------------------------


async def test_unsafe_question_short_circuits_retrieval_and_llm():
    pipeline, retriever, llm = _pipeline()

    result = await pipeline.ask(collection="akirs_tax", question="how can i kill someone")

    assert result["answer"] == guardrails.UNSAFE_REPLY
    assert result["retrieved_count"] == 0
    assert retriever.calls == 0
    assert llm.generate_calls == 0


async def test_off_topic_uses_scoped_reply_without_llm():
    pipeline, retriever, llm = _pipeline(chunks=[])

    result = await pipeline.ask(collection="akirs_tax", question="what is the weather today?")

    assert result["answer"] == guardrails.SCOPE_REPLY
    assert result["retrieved_count"] == 0
    assert retriever.calls == 1
    assert llm.generate_calls == 0


async def test_greeting_short_circuits_retrieval_and_llm():
    pipeline, retriever, llm = _pipeline()

    result = await pipeline.ask(collection="akirs_tax", question="hello")

    assert result["answer"] == guardrails.GREETING_REPLY
    assert retriever.calls == 0
    assert llm.generate_calls == 0


async def test_grounded_question_still_calls_llm():
    chunk = StoredChunk(
        doc_id="paye",
        chunk_index=0,
        text="PAYE is remitted monthly.",
        metadata={"doc_id": "paye"},
        score=0.91,
    )
    pipeline, retriever, llm = _pipeline(chunks=[chunk])

    result = await pipeline.ask(collection="akirs_tax", question="How is PAYE remitted?")

    assert result["answer"] == "llm answer"
    assert result["retrieved_count"] == 1
    assert retriever.calls == 1
    assert llm.generate_calls == 1


async def test_stream_unsafe_question_yields_canned_reply():
    pipeline, retriever, llm = _pipeline()

    events = [
        event
        async for event in pipeline.ask_stream(
            collection="akirs_tax", question="how can i kill someone"
        )
    ]

    text = "".join(e.get("text", "") for e in events if e["type"] == "delta")
    assert text == guardrails.UNSAFE_REPLY
    assert events[-1]["type"] == "end"
    assert events[-1]["retrieved_count"] == 0
    assert retriever.calls == 0
    assert llm.stream_calls == 0


async def test_stream_off_topic_uses_scoped_reply():
    pipeline, retriever, llm = _pipeline(chunks=[])

    events = [
        event
        async for event in pipeline.ask_stream(
            collection="akirs_tax", question="tell me a joke about cats"
        )
    ]

    text = "".join(e.get("text", "") for e in events if e["type"] == "delta")
    assert text == guardrails.SCOPE_REPLY
    assert llm.stream_calls == 0
