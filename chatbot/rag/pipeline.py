"""RAG pipeline — orchestrates the full retrieval → generation → citation flow."""

from __future__ import annotations

import logging
import time

from chatbot.config import settings
from chatbot.llm.base import LLMBackend, LLMResponse
from chatbot.llm.ollama_backend import OllamaBackend
from chatbot.rag.prompt_builder import build_prompt
from chatbot.retrieval.retriever import Retriever, format_context
from chatbot.vector_store.base import StoredChunk

logger = logging.getLogger(__name__)


class RAGPipeline:
    """End-to-end RAG pipeline: embed → retrieve → prompt → generate → cite.

    Usage::

        pipeline = RAGPipeline()
        result = await pipeline.ask(
            collection="biographies",
            question="What did Jane Doe study?",
        )
        print(result["answer"])
        for src in result["sources"]:
            print(src["doc_id"], src["excerpt"])
    """

    def __init__(
        self,
        retriever: Retriever | None = None,
        llm: LLMBackend | None = None,
    ) -> None:
        self._retriever = retriever or Retriever()
        self._llm = llm or OllamaBackend()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def ask(
        self,
        collection: str,
        question: str,
        *,
        top_k: int | None = None,
        system_prompt: str | None = None,
        where: dict | None = None,
        temperature: float | None = None,
    ) -> dict:
        """Run the full RAG pipeline.

        Args:
            collection: Which vector store collection to query.
            question: The user's question.
            top_k: Number of chunks to retrieve.
            system_prompt: Optional custom system prompt.
            where: Optional ChromaDB metadata filter.
            temperature: Optional LLM temperature override.

        Returns:
            Dict with keys:
            - ``answer`` (str): The generated answer.
            - ``sources`` (list[dict]): Retrieved sources with excerpts.
            - ``collection`` (str): The collection queried.
            - ``elapsed_ms`` (float): Total processing time.
            - ``retrieved_count`` (int): Number of chunks retrieved.
        """
        t0 = time.monotonic()

        # 1. Retrieve relevant chunks.
        chunks = await self._retriever.retrieve(
            collection=collection,
            question=question,
            top_k=top_k,
            where=where,
        )

        if not chunks:
            return {
                "answer": "I don't have any information in the provided context to answer that.",
                "sources": [],
                "collection": collection,
                "elapsed_ms": (time.monotonic() - t0) * 1000,
                "retrieved_count": 0,
            }

        # 2. Format context.
        context = format_context(chunks)

        # 3. Build prompts.
        sys_prompt, user_context = build_prompt(
            question=question,
            context=context,
            system_prompt=system_prompt,
        )

        # 4. Generate.
        response: LLMResponse = await self._llm.generate(
            system_prompt=sys_prompt,
            context=user_context,
            question=question,
            temperature=temperature,
        )

        # 5. Build source citations.
        sources = _build_sources(chunks)

        elapsed_ms = (time.monotonic() - t0) * 1000
        logger.info(
            "RAG query complete: '%s' → %d chunks, %.0f ms.",
            question[:80],
            len(chunks),
            elapsed_ms,
        )

        return {
            "answer": response.content,
            "sources": sources,
            "collection": collection,
            "elapsed_ms": elapsed_ms,
            "retrieved_count": len(chunks),
        }

    async def health_check(self) -> dict:
        """Check the health of both the LLM and vector store."""
        llm_ok = await self._llm.health_check()
        collections = await self._retriever._store.list_collections()
        return {
            "llm_ok": llm_ok,
            "model": settings.ollama_model,
            "collections": collections,
            "collection_counts": {
                c: await self._retriever._store.collection_count(c)
                for c in collections
            },
        }

    # ------------------------------------------------------------------
    # Convenience accessors
    # ------------------------------------------------------------------

    @property
    def retriever(self) -> Retriever:
        return self._retriever

    @property
    def llm(self) -> LLMBackend:
        return self._llm


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _build_sources(chunks: list[StoredChunk]) -> list[dict]:
    """Build source citation dicts from retrieved chunks."""
    sources: list[dict] = []
    seen: set[str] = set()
    for c in chunks:
        key = f"{c.doc_id}:{c.chunk_index}"
        if key in seen:
            continue
        seen.add(key)
        sources.append({
            "doc_id": c.doc_id,
            "chunk_index": c.chunk_index,
            "excerpt": c.text[:300],
            "score": round(c.score, 4),
            "metadata": c.metadata,
        })
    return sources
