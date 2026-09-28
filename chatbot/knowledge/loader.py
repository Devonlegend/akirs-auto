"""Auto-ingest the AKIRS tax knowledge base from markdown files.

This reads every ``*.md`` file under the knowledge directory and feeds it
through the standard ingestion pipeline into a dedicated collection (default
``akirs_tax``). It runs at backend startup so the AKIRS Assistant always has
the current knowledge-base content available for retrieval.

The placeholder files shipped in ``chatbot/knowledge/`` are scaffolding — drop
official AKIRS content into them and it will be picked up on the next startup.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from chatbot.config import settings
from chatbot.ingestion.ingestor import Ingestor

logger = logging.getLogger(__name__)

# Marker file recording the hash of the knowledge dir at the last successful
# ingest. Stored next to the persisted vector DB so it survives restarts on
# the same volume; when the hash matches we skip the wipe+re-embed (~40s).
_HASH_FILENAME = ".kb_ingest_hash"


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

    # Skip the wipe+re-embed when the knowledge dir is unchanged since the
    # last successful ingest AND the collection is still populated. On
    # multi-worker/ephemeral deployments the hash file lives on the vector-DB
    # volume, so only the first boot after a content change pays the cost.
    current_hash = _hash_knowledge_dir(knowledge_dir)
    hash_file = Path(settings.vector_db_path) / _HASH_FILENAME
    previous_hash = _read_text_quietly(hash_file)
    existing_count = await ingestor.store.collection_count(collection)
    if (
        previous_hash == current_hash
        and existing_count > 0
    ):
        logger.info(
            "KB unchanged (hash %s, %d chunks present) — skipping re-ingest.",
            current_hash[:8],
            existing_count,
        )
        return {
            "collection": collection,
            "files": len(list(knowledge_dir.glob('*.md'))),
            "chunks": existing_count,
            "skipped": True,
        }

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
    hash_file.write_text(current_hash, encoding="utf-8")
    return {"collection": collection, "files": len(files), "chunks": total_chunks}


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _hash_knowledge_dir(knowledge_dir: Path) -> str:
    """Hash the names + contents of every ``*.md`` file in *knowledge_dir*.

    Stable across runs and platforms; renames and edits both change the hash.
    """
    h = hashlib.sha256()
    for path in sorted(knowledge_dir.glob("*.md")):
        h.update(path.name.encode("utf-8"))
        try:
            h.update(path.read_bytes())
        except OSError:
            continue
    return h.hexdigest()


def _read_text_quietly(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
