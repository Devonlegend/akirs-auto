"""Abstract vector store interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class StoredChunk:
    """A chunk returned from a vector store query."""

    doc_id: str
    chunk_index: int
    text: str
    metadata: dict = field(default_factory=dict)
    score: float = 0.0


class VectorStore(ABC):
    """Abstract interface for a vector store.

    Implementations must provide methods for adding chunks with embeddings
    and querying by embedding vector.  ChromaDB is the default implementation
    (see :class:`chroma_store.ChromaVectorStore`).
    """

    @abstractmethod
    async def add(
        self,
        collection: str,
        chunks: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict],
        ids: list[str],
    ) -> None:
        """Add *chunks* with their *embeddings* and *metadatas* to *collection*.

        Args:
            collection: The collection name (created if it doesn't exist).
            chunks: The text chunks.
            embeddings: Corresponding embedding vectors (same length as *chunks*).
            metadatas: Metadata dicts per chunk.
            ids: Unique IDs per chunk.
        """
        ...

    @abstractmethod
    async def query(
        self,
        collection: str,
        query_embedding: list[float],
        top_k: int = 10,
        where: dict | None = None,
    ) -> list[StoredChunk]:
        """Query *collection* with *query_embedding*.

        Args:
            collection: The collection name.
            query_embedding: The query vector.
            top_k: Number of results to return.
            where: Optional ChromaDB metadata filter dict.

        Returns:
            List of :class:`StoredChunk` ordered by relevance (highest first).
        """
        ...

    @abstractmethod
    async def delete_collection(self, collection: str) -> None:
        """Delete an entire collection."""
        ...

    @abstractmethod
    async def delete_document(self, collection: str, doc_id: str) -> None:
        """Delete all chunks belonging to *doc_id* from *collection*.

        Best-effort: implementations should not raise if the collection or
        document does not exist.
        """
        ...

    @abstractmethod
    async def list_collections(self) -> list[str]:
        """Return the names of all existing collections."""
        ...

    @abstractmethod
    async def collection_count(self, collection: str) -> int:
        """Return the number of chunks stored in *collection*."""
        ...
