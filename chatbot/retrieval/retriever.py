"""Semantic retriever — embeds queries and fetches relevant chunks from the vector store."""

from __future__ import annotations

import logging
import re
import time

from chatbot.config import settings
from chatbot.embeddings.embedder import Embedder
from chatbot.vector_store.base import StoredChunk, VectorStore
from chatbot.vector_store.chroma_store import ChromaVectorStore

logger = logging.getLogger(__name__)

# Fast-path: greetings / capability questions don't need retrieval or embedding.
_GREETING_RE = re.compile(
    r"^(hi|hello|hey|good\s*(morning|afternoon|evening)|yo|what\s+can\s+you\s+do"
    r"|who\s+are\s+you|how\s+are\s+you|thanks|thank\s*you)\b.*$",
    re.IGNORECASE,
)

# Simple TTL cache for normalized query embeddings (identical questions won't
# re-run the embedding model for an hour).
_EMBED_CACHE: dict[str, tuple[float, list[float]]] = {}
_EMBED_CACHE_TTL = 3600.0
_EMBED_CACHE_MAX = 256


def is_greeting(question: str) -> bool:
    """True for short conversational/greeting inputs that skip retrieval."""
    q = question.strip()
    if not q or len(q.split()) > 12:
        return False
    return bool(_GREETING_RE.match(q))


class Retriever:
    """Embeds a user query and retrieves the most relevant chunks.

    Usage::

        retriever = Retriever()
        chunks = await retriever.retrieve(
            collection="biographies",
            question="Where was Jane Doe born?",
            top_k=5,
        )
    """

    def __init__(
        self,
        vector_store: VectorStore | None = None,
        embedder: Embedder | None = None,
    ) -> None:
        self._store = vector_store or ChromaVectorStore()
        self._embedder = embedder or Embedder()

    async def retrieve(
        self,
        collection: str,
        question: str,
        top_k: int | None = None,
        where: dict | None = None,
    ) -> list[StoredChunk]:
        """Retrieve relevant chunks for *question* from *collection*.

        Args:
            collection: The collection to query.
            question: The user's natural-language question.
            top_k: Number of chunks to retrieve (default from settings).
            where: Optional ChromaDB metadata filter.

        Returns:
            List of :class:`StoredChunk` ordered by relevance.
        """
        top_k = top_k if top_k is not None else settings.top_k

        if not question.strip():
            return []

        # Greetings / small talk short-circuit before we spend time embedding.
        if is_greeting(question):
            return []

        query_vec = await self._cached_embed(question)
        chunks = await self._store.query(
            collection=collection,
            query_embedding=query_vec,
            top_k=top_k,
            where=where,
        )

        logger.debug(
            "Retrieved %d chunks from '%s' for query: %s",
            len(chunks),
            collection,
            question[:80],
        )
        return chunks

    async def _cached_embed(self, question: str) -> list[float]:
        """Embed *question*, serving cached results for repeats within TTL."""
        key = " ".join(question.lower().split())
        now = time.monotonic()
        hit = _EMBED_CACHE.get(key)
        if hit and now - hit[0] < _EMBED_CACHE_TTL:
            return hit[1]
        vec = await self._embedder.embed_query(question)
        if len(_EMBED_CACHE) >= _EMBED_CACHE_MAX:
            _EMBED_CACHE.clear()
        _EMBED_CACHE[key] = (now, vec)
        return vec

    @property
    def store(self) -> VectorStore:
        """The underlying vector store (for stats / health checks)."""
        return self._store


def format_context(chunks: list[StoredChunk], *, max_tokens: int = 1200) -> str:

    if not chunks:
        return "No relevant context found."

    parts: list[str] = []
    char_budget = max_tokens * 4  # rough heuristic

    for i, c in enumerate(chunks):
        source = c.metadata.get("doc_id", "unknown")[:20]
        label = f"[Source: {source}, chunk {c.chunk_index}]"
        block = f"{label}\n{c.text}"
        if sum(len(p) for p in parts) + len(block) > char_budget:
            # If we'd run over budget, stop — but always include at least one chunk.
            if parts:
                break
        parts.append(block)

    return "\n\n---\n\n".join(parts)
