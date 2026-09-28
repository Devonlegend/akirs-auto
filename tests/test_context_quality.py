"""Tests that heading-only chunks are dropped from retrieval context.

A lone markdown heading ("## Overview") embeds close to its page's topic, so it
ranks highly and occupies a context slot while answering nothing. Feeding those
stubs to a small LLM made it abstain even when the answer was present, so they
are filtered at ingest and again when the pipeline assembles context.
"""

from __future__ import annotations

import pytest

from chatbot.llm.base import LLMResponse
from chatbot.nlp.cleaner import is_heading_only
from chatbot.rag import pipeline as pipeline_module
from chatbot.rag.pipeline import RAGPipeline
from chatbot.vector_store.base import StoredChunk


@pytest.fixture(autouse=True)
def _clear_pipeline_cache():
    """The pipeline cache is module-level; isolate tests from each other."""
    pipeline_module._CACHE.clear()
    yield
    pipeline_module._CACHE.clear()


class _FakeLLM:
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
    def __init__(self, chunks: list[StoredChunk]) -> None:
        self._chunks = chunks

    async def retrieve(self, **kwargs) -> list[StoredChunk]:
        return self._chunks


def _chunk(doc_id: str, index: int, text: str, score: float = 0.8) -> StoredChunk:
    return StoredChunk(
        doc_id=doc_id,
        chunk_index=index,
        text=text,
        metadata={"doc_id": doc_id},
        score=score,
    )


def _pipeline(chunks: list[StoredChunk]):
    llm = _FakeLLM()
    return RAGPipeline(retriever=_FakeRetriever(chunks), llm=llm), llm


# ---------------------------------------------------------------------------
# is_heading_only
# ---------------------------------------------------------------------------


def test_heading_only_detects_markdown_stubs():
    assert is_heading_only("# AKIRS Contact Details and Offices -- Akwa Ibom State")
    assert is_heading_only("## What AKIRS is")
    assert is_heading_only("### Overview\n---")
    assert is_heading_only("---")


def test_heading_only_keeps_real_prose():
    assert not is_heading_only("Registration is done online through IbomTax.")
    assert not is_heading_only(
        "## Online channels\n- Official website: akirs.ak.gov.ng"
    )
    assert not is_heading_only("PAYE is remitted monthly.")


# ---------------------------------------------------------------------------
# pipeline wiring
# ---------------------------------------------------------------------------


async def test_heading_stubs_are_dropped_from_context():
    real = _chunk("contact-offices", 10, "- Official website: akirs.ak.gov.ng")
    stub = _chunk("contact-offices", 0, "# AKIRS Contact Details and Offices")
    pipeline, llm = _pipeline([stub, real])

    result = await pipeline.ask(collection="akirs_tax", question="wheres akirs website")

    assert result["answer"] == "llm answer"
    assert result["retrieved_count"] == 1
    assert [s["doc_id"] for s in result["sources"]] == ["contact-offices"]
    assert llm.generate_calls == 1


async def test_only_heading_stubs_falls_back_to_scoped_reply():
    pipeline, llm = _pipeline([_chunk("overview", 1, "## What AKIRS is")])

    result = await pipeline.ask(collection="akirs_tax", question="wheres akirs website")

    assert result["retrieved_count"] == 0
    assert llm.generate_calls == 0


async def test_stream_drops_heading_stubs():
    real = _chunk("contact-offices", 10, "- Official website: akirs.ak.gov.ng")
    stub = _chunk("contact-offices", 0, "# AKIRS Contact Details and Offices")
    pipeline, llm = _pipeline([stub, real])

    events = [
        e
        async for e in pipeline.ask_stream(
            collection="akirs_tax", question="wheres akirs website"
        )
    ]

    sources = next(e for e in events if e["type"] == "sources")
    assert [s["doc_id"] for s in sources["sources"]] == ["contact-offices"]
    assert llm.stream_calls == 1
