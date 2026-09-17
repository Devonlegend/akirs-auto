"""RAG pipeline — orchestrates the full retrieval → generation → citation flow."""

from __future__ import annotations

import logging
import time

from chatbot.config import settings
from chatbot.llm.base import LLMBackend, LLMResponse
from chatbot.llm.ollama_backend import OllamaBackend
from chatbot.rag.prompt_builder import GENERAL_SYSTEM_PROMPT, build_prompt
from chatbot.retrieval.retriever import Retriever, format_context, is_greeting
from chatbot.vector_store.base import StoredChunk

logger = logging.getLogger(__name__)

# Simple bounded TTL cache keyed by (collection, question, top_k) so identical
# questions within a short window don't re-run embedding + retrieval + LLM.
_CACHE: dict[tuple, tuple[float, dict]] = {}
_CACHE_TTL = 300.0  # 5 minutes
_CACHE_MAX = 128


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

        # Greeting / small talk: skip retrieval+embedding entirely and answer
        # conversationally with the general prompt (no sources).
        if is_greeting(question):
            response = await self._llm.generate(
                system_prompt=GENERAL_SYSTEM_PROMPT,
                context="",
                question=question,
                temperature=temperature,
            )
            return {
                "answer": response.content,
                "sources": [],
                "collection": collection,
                "elapsed_ms": (time.monotonic() - t0) * 1000,
                "retrieved_count": 0,
            }

        # Cache hit: identical question recently answered → return it directly.
        key = _cache_key(collection, question, top_k)
        now = time.monotonic()
        hit = _CACHE.get(key)
        if hit and now - hit[0] < _CACHE_TTL:
            cached = dict(hit[1])
            cached["elapsed_ms"] = (now - hit[0]) * 1000  # reflect cache time
            cached["cached"] = True
            return cached

        result = await self._run_ask(
            collection=collection,
            question=question,
            top_k=top_k,
            system_prompt=system_prompt,
            where=where,
            temperature=temperature,
            t0=t0,
        )

        if len(_CACHE) >= _CACHE_MAX:
            _CACHE.clear()
        _CACHE[key] = (time.monotonic(), result)
        return result

    async def _run_ask(
        self,
        collection: str,
        question: str,
        *,
        top_k: int | None = None,
        system_prompt: str | None = None,
        where: dict | None = None,
        temperature: float | None = None,
        t0: float,
    ) -> dict:
        """Core (uncached) RAG path: retrieve → filter → prompt → generate."""
        # 1. Retrieve relevant chunks.
        chunks = await self._retriever.retrieve(
            collection=collection,
            question=question,
            top_k=top_k,
            where=where,
        )

        # 1b. Drop low-relevance matches so off-topic queries (greetings, small
        # talk) don't get answered against junk context.
        relevant = [c for c in chunks if c.score >= settings.relevance_threshold]
        if len(relevant) != len(chunks):
            logger.debug(
                "Filtered %d/%d chunks below relevance threshold %.2f.",
                len(chunks) - len(relevant),
                len(chunks),
                settings.relevance_threshold,
            )

        if not relevant:
            # No relevant documents — fall back to a general conversational
            # answer (greetings, small talk, simple questions) instead of refusing.
            response = await self._llm.generate(
                system_prompt=GENERAL_SYSTEM_PROMPT,
                context="",
                question=question,
                temperature=temperature,
            )
            return {
                "answer": response.content,
                "sources": [],
                "collection": collection,
                "elapsed_ms": (time.monotonic() - t0) * 1000,
                "retrieved_count": 0,
            }

        # 2. Format context.
        context = format_context(relevant)

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
        sources = _build_sources(relevant)

        elapsed_ms = (time.monotonic() - t0) * 1000
        logger.info(
            "RAG query complete: '%s' → %d chunks, %.0f ms.",
            question[:80],
            len(relevant),
            elapsed_ms,
        )

        return {
            "answer": response.content,
            "sources": sources,
            "collection": collection,
            "elapsed_ms": elapsed_ms,
            "retrieved_count": len(relevant),
        }

    async def ask_stream(
        self,
        collection: str,
        question: str,
        *,
        top_k: int | None = None,
        system_prompt: str | None = None,
        where: dict | None = None,
        temperature: float | None = None,
    ):
        """Streamed variant of :meth:`ask`.

        Yields a sequence of dicts consumed by the SSE endpoint:
        - ``{"type": "start", ...}``   (metadata: collection, question)
        - ``{"type": "sources", ...}`` (citations ready before TTFB)
        - ``{"type": "delta", ...}``   (one token fragment)
        - ``{"type": "end", ...}``     (elapsed_ms, retrieved_count)

        NOT cached (one-shot streaming) and preserves the greeting fast-path.
        """
        t0 = time.monotonic()
        yield {"type": "start", "collection": collection}

        # Greeting fast-path: no retrieval/sources — just stream a general reply.
        if is_greeting(question):
            async for delta, _final in self._llm.generate_stream(
                system_prompt=GENERAL_SYSTEM_PROMPT,
                context="",
                question=question,
                temperature=temperature,
            ):
                if delta:
                    yield {"type": "delta", "text": delta}
            yield {"type": "end", "elapsed_ms": (time.monotonic() - t0) * 1000,
                   "retrieved_count": 0}
            return

        chunks = await self._retriever.retrieve(
            collection=collection,
            question=question,
            top_k=top_k,
            where=where,
        )
        relevant = [c for c in chunks if c.score >= settings.relevance_threshold]

        if not relevant:
            async for delta, _final in self._llm.generate_stream(
                system_prompt=GENERAL_SYSTEM_PROMPT,
                context="",
                question=question,
                temperature=temperature,
            ):
                if delta:
                    yield {"type": "delta", "text": delta}
            yield {"type": "end", "elapsed_ms": (time.monotonic() - t0) * 1000,
                   "retrieved_count": 0}
            return

        context = format_context(relevant)
        sys_prompt, user_context = build_prompt(
            question=question,
            context=context,
            system_prompt=system_prompt,
        )

        # Emit sources immediately so the frontend can render citations while the
        # model is still generating.
        yield {"type": "sources", "sources": _build_sources(relevant)}

        async for delta, _final in self._llm.generate_stream(
            system_prompt=sys_prompt,
            context=user_context,
            question=question,
            temperature=temperature,
        ):
            if delta:
                yield {"type": "delta", "text": delta}

        yield {"type": "end",
               "elapsed_ms": (time.monotonic() - t0) * 1000,
               "retrieved_count": len(relevant)}

    async def prepare(self) -> None:
        """Ensure the LLM backend is ready (server up, model pulled, warmed).

        No-op for backends that don't implement ``ensure_ready``.
        """
        ensure_ready = getattr(self._llm, "ensure_ready", None)
        if ensure_ready is not None:
            await ensure_ready()

    async def aclose(self) -> None:
        """Release backend resources (e.g. the LLM's HTTP client).

        No-op for backends that don't implement ``close``.
        """
        close = getattr(self._llm, "close", None)
        if close is not None:
            await close()

    async def health_check(self) -> dict:
        """Check the health of both the LLM and vector store."""
        store = self._retriever.store
        llm_ok = await self._llm.health_check()
        collections = await store.list_collections()
        return {
            "llm_ok": llm_ok,
            "model": settings.ollama_model,
            "collections": collections,
            "collection_counts": {
                c: await store.collection_count(c)
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


def _cache_key(collection: str, question: str, top_k: int | None) -> tuple:
    """Stable cache key for the pipeline query cache."""
    return (collection, " ".join(question.lower().split()), top_k or settings.top_k)


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
