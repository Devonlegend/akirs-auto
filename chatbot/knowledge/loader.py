"""Auto-ingest the AKIRS tax knowledge base from markdown files.

This reads every ``*.md`` file under the knowledge directory and feeds it
through the standard ingestion pipeline into a dedicated collection (default
``akirs_tax``). It runs at backend startup so the AKIRS Assistant always has
the current knowledge-base content available for retrieval.

The placeholder files shipped in ``chatbot/knowledge/`` are scaffolding — drop
official AKIRS content into them and it will be picked up on the next startup.
"""

from __future__ import annotations

import logging
from pathlib import Path

from chatbot.config import settings
from chatbot.ingestion.ingestor import Ingestor

logger = logging.getLogger(__name__)


async def ingest_knowledge_base(
    ingestor: Ingestor,
    *,
    collection: str | None = None,
    knowledge_dir: Path | None = None,
) -> dict:
    """Ingest every ``.md`` file in *knowledge_dir* into *collection*.

    Idempotent: the target collection is dropped and rebuilt on every call so
    edits to the markdown files are reflected and stale chunks never linger.

    Args:
        ingestor: The shared :class:`Ingestor` (reuses its vector store).
        collection: Target collection. Defaults to ``settings.knowledge_collection``.
        knowledge_dir: Source folder. Defaults to ``settings.knowledge_dir``.

    Returns:
        Dict with keys ``collection``, ``files``, and ``chunks``.
    """
    collection = collection or settings.knowledge_collection
    knowledge_dir = Path(knowledge_dir or settings.knowledge_dir)

    if not knowledge_dir.is_dir():
        logger.warning(
            "Knowledge dir %s does not exist — skipping KB ingest.", knowledge_dir
        )
        return {"collection": collection, "files": 0, "chunks": 0}

    # Wipe + rebuild so edited files don't leave stale chunks behind.
    await ingestor.store.delete_collection(collection)

    files = sorted(knowledge_dir.glob("*.md"))
    total_chunks = 0
    for path in files:
        topic = path.stem
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            logger.warning("Could not read KB file %s: %s", path.name, exc)
            continue

        result = await ingestor.ingest(
            collection=collection,
            text=text,
            metadata={"source": "akirs_knowledge_base", "topic": topic},
            doc_id=topic,
        )
        chunks = result["chunks_created"]
        total_chunks += chunks
        if chunks == 0:
            logger.warning(
                "KB file %s produced 0 chunks (likely too sparse — add prose).",
                path.name,
            )
        else:
            logger.info("KB ingest %s -> %d chunks.", path.name, chunks)

    logger.info(
        "KB ingest complete: %d files, %d chunks into '%s'.",
        len(files),
        total_chunks,
        collection,
    )
    return {"collection": collection, "files": len(files), "chunks": total_chunks}
