"""Ingestion pipeline — takes raw text and feeds it into the vector store."""

from __future__ import annotations

import logging
import time
import uuid

from chatbot.embeddings.embedder import Embedder
from chatbot.nlp.chunker import TextChunker
from chatbot.nlp.cleaner import clean_text, is_noise
from chatbot.vector_store.base import VectorStore
from chatbot.vector_store.chroma_store import ChromaVectorStore

logger = logging.getLogger(__name__)


class Ingestor:
    """Generic text ingestion pipeline.

    Takes raw text + metadata, cleans it, chunks it, embeds the chunks,
    and persists them to a named collection in the vector store.

    This is the single entry point for ALL data — whether it's a biography,
    scraper output, meeting notes, or anything else.

    Usage::

        ingestor = Ingestor()
        result = await ingestor.ingest(
            collection="biographies",
            text="Jane Doe was born in Lagos ...",
            metadata={"person": "Jane Doe", "type": "biography"},
        )
        print(result["chunks_created"])  # → 3
    """

    def __init__(
        self,
        *,
        vector_store: VectorStore | None = None,
        embedder: Embedder | None = None,
        chunker: TextChunker | None = None,
    ) -> None:
        self._store = vector_store or ChromaVectorStore()
        self._embedder = embedder or Embedder()
        self._chunker = chunker or TextChunker()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def ingest(
        self,
        collection: str,
        text: str,
        *,
        metadata: dict | None = None,
        doc_id: str | None = None,
        skip_noise: bool = True,
    ) -> dict:
        """Ingest a single document into *collection*.

        Args:
            collection: Target collection name.
            text: Raw text content.
            metadata: Arbitrary key-value metadata to attach to every chunk
                from this document.
            doc_id: Optional external document ID.  Auto-generated if omitted.
            skip_noise: If ``True`` (default), skip chunks that look like noise.

        Returns:
            Dict with keys ``collection``, ``doc_id``, ``chunks_created``,
            ``elapsed_ms``.
        """
        t0 = time.monotonic()
        doc_id = doc_id or str(uuid.uuid4())
        metadata = dict(metadata or {})

        # 1. Clean.
        cleaned = clean_text(text)
        if not cleaned:
            return {
                "collection": collection,
                "doc_id": doc_id,
                "chunks_created": 0,
                "elapsed_ms": (time.monotonic() - t0) * 1000,
            }

        # 2. Chunk.
        chunks = self._chunker.chunk(cleaned)
        if skip_noise:
            chunks = [c for c in chunks if not is_noise(c.text)]

        if not chunks:
            return {
                "collection": collection,
                "doc_id": doc_id,
                "chunks_created": 0,
                "elapsed_ms": (time.monotonic() - t0) * 1000,
            }

        # 3. Embed.
        chunk_texts = [c.text for c in chunks]
        embeddings = await self._embedder.embed(chunk_texts)

        # 4. Build metadata + IDs per chunk.
        metadatas: list[dict] = []
        ids: list[str] = []
        for c in chunks:
            chunk_meta = {
                "doc_id": doc_id,
                "chunk_index": c.index,
                "token_count": c.token_count,
                **metadata,
            }
            metadatas.append(chunk_meta)
            ids.append(f"{doc_id}:{c.index}")

        # 5. Store.
        await self._store.add(
            collection=collection,
            chunks=chunk_texts,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids,
        )

        elapsed_ms = (time.monotonic() - t0) * 1000
        logger.info(
            "Ingested doc %s → %d chunks into '%s' (%.0f ms).",
            doc_id,
            len(chunks),
            collection,
            elapsed_ms,
        )

        return {
            "collection": collection,
            "doc_id": doc_id,
            "chunks_created": len(chunks),
            "elapsed_ms": elapsed_ms,
        }

    async def ingest_many(
        self,
        collection: str,
        documents: list[dict],
    ) -> list[dict]:
        """Ingest multiple documents in sequence.

        Args:
            collection: Target collection name.
            documents: List of dicts, each with ``text`` (required),
                optional ``metadata`` and ``doc_id``.

        Returns:
            List of result dicts (same format as :meth:`ingest`).
        """
        results: list[dict] = []
        for doc in documents:
            result = await self.ingest(
                collection=collection,
                text=doc["text"],
                metadata=doc.get("metadata"),
                doc_id=doc.get("doc_id"),
            )
            results.append(result)
        return results

    async def delete_document(self, collection: str, doc_id: str) -> None:
        """Delete all chunks belonging to *doc_id* from *collection*.

        Best-effort: relies on ChromaDB's delete-by-metadata filter.
        """
        store = self._store
        if not isinstance(store, ChromaVectorStore):
            logger.warning("delete_document only supported for ChromaVectorStore.")
            return
        try:
            coll = store._client.get_collection(collection)
            coll.delete(where={"doc_id": doc_id})
            logger.info("Deleted chunks for doc_id=%s from '%s'.", doc_id, collection)
        except Exception:
            logger.warning(
                "Could not delete doc_id=%s — collection '%s' may not exist.",
                doc_id,
                collection,
            )

    # ------------------------------------------------------------------
    # Convenience properties
    # ------------------------------------------------------------------

    @property
    def store(self) -> VectorStore:
        return self._store

    @property
    def embedder(self) -> Embedder:
        return self._embedder
