"""SentenceTransformer embedder for turning text chunks into vector embeddings."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from sentence_transformers import SentenceTransformer

from chatbot.config import settings

logger = logging.getLogger(__name__)


class Embedder:
    """Wraps a ``SentenceTransformer`` model for synchronous / async embedding.

    The underlying model is loaded once and kept in memory.  Encoding calls
    are offloaded to a thread pool via :func:`asyncio.to_thread` to avoid
    blocking the event loop.

    Usage::

        embedder = Embedder()
        vectors = await embedder.embed(["text one", "text two"])
        # vectors.shape → (2, 384)
    """

    def __init__(
        self,
        model_name: str | None = None,
        *,
        cache_dir: str | Path | None = None,
    ) -> None:
        self._model_name = model_name or settings.embedding_model
        self._model: SentenceTransformer | None = None
        self._cache_dir = str(cache_dir) if cache_dir else None

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Encode *texts* into embedding vectors (async-friendly).

        Args:
            texts: List of text strings to embed.  Batch size is handled
                internally by the model.

        Returns:
            A list of vectors, each being a list of floats with dimension
            determined by the model (384 for ``all-MiniLM-L6-v2``).
        """
        if not texts:
            return []

        model = await asyncio.to_thread(self._get_or_load_model)
        # sentence-transformers encode is synchronous — run in thread.
        embeddings = await asyncio.to_thread(
            model.encode,
            texts,
            batch_size=32,
            show_progress_bar=False,
            normalize_embeddings=True,
        )
        return embeddings.tolist()

    async def embed_query(self, text: str) -> list[float]:
        """Embed a single query text. Convenience wrapper around :meth:`embed`."""
        results = await self.embed([text])
        return results[0]

    @property
    def dimension(self) -> int:
        """Return the embedding vector dimension."""
        model = self._get_or_load_model()
        return self._embedding_dimension(model)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _get_or_load_model(self) -> SentenceTransformer:
        if self._model is None:
            logger.info("Loading embedding model %s ...", self._model_name)
            self._model = SentenceTransformer(
                self._model_name,
                cache_folder=self._cache_dir,
            )
            logger.info(
                "Embedding model loaded (dim=%d).",
                self._embedding_dimension(self._model),
            )
        return self._model

    @staticmethod
    def _embedding_dimension(model: SentenceTransformer) -> int:
        """Return the embedding dimension, handling the St v3/v5 method rename."""
        getter = getattr(model, "get_embedding_dimension", None)
        if getter is None:
            getter = model.get_sentence_embedding_dimension
        return getter()
