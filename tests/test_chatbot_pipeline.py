"""Tests for the RAG pipeline — relevance threshold + general-chat fallback.

Uses in-process fakes (no Ollama, no ChromaDB, no network).
"""

from __future__ import annotations

from chatbot.config import settings
from chatbot.llm.base import LLMBackend, LLMResponse
from chatbot.rag.pipeline import RAGPipeline
from chatbot.rag.prompt_builder import DEFAULT_SYSTEM_PROMPT, GENERAL_SYSTEM_PROMPT
from chatbot.vector_store.base import StoredChunk


class FakeRetriever:
    """Returns a fixed list of chunks, ignoring the query."""

    def __init__(self, chunks: list[StoredChunk]) -> None:
        self._chunks = chunks

    async def retrieve(self, collection, question, top_k=None, where=None):
        return list(self._chunks)


class SpyLLM(LLMBackend):
    """Records the system prompt it was last called with."""

    def __init__(self) -> None:
        self.last_system_prompt: str | None = None
        self.calls = 0

    async def generate(self, system_prompt, context, question, *, temperature=None, max_tokens=None):
        self.last_system_prompt = system_prompt
        self.calls += 1
        return LLMResponse(content="fake answer", model="fake")

    async def health_check(self) -> bool:
        return True


def _chunk(score: float, idx: int = 0) -> StoredChunk:
    return StoredChunk(
        doc_id=f"doc{idx}",
        chunk_index=idx,
        text=f"chunk text {idx}",
        metadata={"doc_id": f"doc{idx}"},
        score=score,
    )


async def test_low_relevance_chunks_are_filtered():
    # One chunk above the threshold, one below — only the strong one is used.
    above = settings.relevance_threshold + 0.2
    below = settings.relevance_threshold - 0.2
    llm = SpyLLM()
    pipe = RAGPipeline(retriever=FakeRetriever([_chunk(above, 0), _chunk(below, 1)]), llm=llm)

    result = await pipe.ask(collection="c", question="real question")

    assert result["retrieved_count"] == 1
    assert len(result["sources"]) == 1
    assert llm.last_system_prompt == DEFAULT_SYSTEM_PROMPT


async def test_all_below_threshold_falls_back_to_general():
    below = settings.relevance_threshold - 0.1
    llm = SpyLLM()
    pipe = RAGPipeline(retriever=FakeRetriever([_chunk(below, 0), _chunk(below, 1)]), llm=llm)

    result = await pipe.ask(collection="c", question="hey")

    assert result["retrieved_count"] == 0
    assert result["sources"] == []
    assert llm.last_system_prompt == GENERAL_SYSTEM_PROMPT


async def test_empty_retrieval_falls_back_to_general():
    llm = SpyLLM()
    pipe = RAGPipeline(retriever=FakeRetriever([]), llm=llm)

    result = await pipe.ask(collection="c", question="hello there")

    assert result["retrieved_count"] == 0
    assert llm.last_system_prompt == GENERAL_SYSTEM_PROMPT
    assert result["answer"] == "fake answer"


async def test_strict_path_returns_sources():
    strong = settings.relevance_threshold + 0.3
    llm = SpyLLM()
    pipe = RAGPipeline(
        retriever=FakeRetriever([_chunk(strong, 0), _chunk(strong, 1)]), llm=llm
    )

    result = await pipe.ask(collection="c", question="real question")

    assert result["retrieved_count"] == 2
    assert len(result["sources"]) == 2
    assert llm.last_system_prompt == DEFAULT_SYSTEM_PROMPT
