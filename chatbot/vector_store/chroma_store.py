"""ChromaDB vector store — persistent local storage with metadata filtering."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import override

import chromadb
from chromadb.config import Settings as ChromaSettings

from chatbot.config import settings
from chatbot.vector_store.base import StoredChunk, VectorStore

logger = logging.getLogger(__name__)


class ChromaVectorStore(VectorStore):
    """Vector store backed by ChromaDB with persistent local storage.

    Each "collection" in the RAG chatbot maps 1:1 to a ChromaDB collection.
    All collections live under a single ChromaDB client pointed at
    ``settings.vector_db_path``.

    Usage::

        store = ChromaVectorStore()
        await store.add("biographies", chunks, embeddings, metadatas, ids)
        results = await store.query("biographies", query_vec, top_k=5)
    """

    def __init__(self, persist_dir: str | Path | None = None) -> None:
        self._persist_dir = str(persist_dir or settings.vector_db_path)
        Path(self._persist_dir).mkdir(parents=True, exist_ok=True)

        self._client = chromadb.PersistentClient(
            path=self._persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        logger.info("ChromaDB client initialized at %s", self._persist_dir)

    # ------------------------------------------------------------------
    # VectorStore implementation
    # ------------------------------------------------------------------

    @override
    async def add(
        self,
        collection: str,
        chunks: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict],
        ids: list[str],
    ) -> None:
        coll = await asyncio.to_thread(self._get_or_create_collection, collection)

        # ChromaDB metadata values must be str, int, float, or bool.
        clean_metas = [_sanitize_metadata(m) for m in metadatas]

        await asyncio.to_thread(
            coll.add,
            ids=ids,
            documents=chunks,
            embeddings=embeddings,
            metadatas=clean_metas,
        )
        logger.debug("Added %d chunks to collection '%s'.", len(chunks), collection)

    @override
    async def query(
        self,
        collection: str,
        query_embedding: list[float],
        top_k: int = 10,
        where: dict | None = None,
    ) -> list[StoredChunk]:
        try:
            coll = self._client.get_collection(collection)
        except (ValueError, Exception):
            return []

        kwargs: dict = {"query_embeddings": [query_embedding], "n_results": top_k}
        if where is not None:
            kwargs["where"] = where

        results = coll.query(**kwargs)

        chunks: list[StoredChunk] = []
        if results["ids"] and results["ids"][0]:
            for i, chunk_id in enumerate(results["ids"][0]):
                chunks.append(
                    StoredChunk(
                        doc_id=results["metadatas"][0][i].get("doc_id", "unknown"),
                        chunk_index=int(
                            results["metadatas"][0][i].get("chunk_index", 0)
                        ),
                        text=results["documents"][0][i]
                        if results["documents"] and results["documents"][0]
                        else "",
                        metadata=results["metadatas"][0][i] or {},
                        score=1.0
                        - (
                            results["distances"][0][i]
                            if results["distances"] and results["distances"][0]
                            else 0.0
                        ),
                    )
                )
        return chunks

    @override
    async def delete_collection(self, collection: str) -> None:
        try:
            self._client.delete_collection(collection)
            logger.info("Deleted collection '%s'.", collection)
        except (ValueError, Exception):
            logger.warning("Collection '%s' does not exist — nothing to delete.", collection)

    @override
    async def list_collections(self) -> list[str]:
        return [c.name for c in self._client.list_collections()]

    @override
    async def collection_count(self, collection: str) -> int:
        try:
            coll = self._client.get_collection(collection)
            return coll.count()
        except (ValueError, Exception):
            return 0

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _get_or_create_collection(self, name: str):
        """Get an existing collection or create it.

        Uses the embedding dimension from the first call to configure the
        collection's HNSW space.  Safe to call repeatedly.
        """
        try:
            return self._client.get_collection(name)
        except (ValueError, Exception):
            logger.info("Creating new ChromaDB collection '%s'.", name)
            return self._client.create_collection(
                name=name,
                metadata={"hnsw:space": "cosine"},
            )


def _sanitize_metadata(meta: dict) -> dict:
    """Ensure all metadata values are ChromaDB-compatible types."""
    clean: dict = {}
    for k, v in meta.items():
        if v is None:
            continue
        if isinstance(v, (str, int, float, bool)):
            clean[k] = v
        else:
            clean[k] = str(v)
    return clean
