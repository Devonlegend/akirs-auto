"""Tests for retrieval helpers — context formatting and blank-query short-circuit.

No embedding model or vector store is loaded (fakes are injected).
"""

from __future__ import annotations

from chatbot.retrieval.retriever import Retriever, format_context
from chatbot.vector_store.base import StoredChunk


def _chunk(idx: int, text: str) -> StoredChunk:
    return StoredChunk(
        doc_id=f"doc{idx}",
        chunk_index=idx,
        text=text,
        metadata={"doc_id": f"doc{idx}"},
        score=1.0,
    )


def test_format_context_empty():
    assert format_context([]) == "No relevant context found."


def test_format_context_includes_source_labels():
    out = format_context([_chunk(0, "hello world")])
    assert "Source: doc0" in out
    assert "hello world" in out


def test_format_context_respects_token_budget():
    # Two large chunks with a tiny budget — only the first should fit.
    big = "word " * 500
    out = format_context([_chunk(0, big), _chunk(1, big)], max_tokens=50)
    assert "doc0" in out
    assert "doc1" not in out


class _ExplodingDep:
    """Any attribute access blows up — proves it was never touched."""

    def __getattr__(self, name):
        raise AssertionError(f"dependency unexpectedly used: {name}")


async def test_retrieve_blank_question_returns_empty():
    retriever = Retriever(vector_store=_ExplodingDep(), embedder=_ExplodingDep())
    assert await retriever.retrieve(collection="c", question="   ") == []
