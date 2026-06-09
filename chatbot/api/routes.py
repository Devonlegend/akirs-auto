"""FastAPI router for the RAG chatbot."""

from __future__ import annotations

import asyncio
import logging
import uuid

from fastapi import APIRouter, HTTPException

from chatbot.api.schemas import (
    ChatRequest,
    ChatResponse,
    CollectionInfo,
    CollectionsResponse,
    HealthResponse,
    IngestFromScraperRequest,
    IngestFromScraperResponse,
    IngestRequest,
    IngestResponse,
    SourceCitation,
)
from chatbot.ingestion.ingestor import Ingestor
from chatbot.rag.pipeline import RAGPipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chatbot", tags=["chatbot"])

# ------------------------------------------------------------------
# Module-level singletons (lazy-initialized)
# ------------------------------------------------------------------

_ingestor: Ingestor | None = None
_pipeline: RAGPipeline | None = None


def _get_ingestor() -> Ingestor:
    global _ingestor
    if _ingestor is None:
        _ingestor = Ingestor()
    return _ingestor


def _get_pipeline() -> RAGPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = RAGPipeline()
    return _pipeline


# ------------------------------------------------------------------
# Ingest
# ------------------------------------------------------------------


@router.post("/ingest", response_model=IngestResponse)
async def ingest_text(body: IngestRequest) -> IngestResponse:
    """Feed raw text into a named collection.

    The text is cleaned, chunked, embedded, and stored.  Any metadata
    provided is attached to every chunk from this document.
    """
    ingestor = _get_ingestor()
    result = await ingestor.ingest(
        collection=body.collection,
        text=body.text,
        metadata=body.metadata,
        doc_id=body.doc_id or str(uuid.uuid4()),
    )
    return IngestResponse(**result)


@router.post("/ingest/from-scraper", response_model=IngestFromScraperResponse)
async def ingest_from_scraper(body: IngestFromScraperRequest) -> IngestFromScraperResponse:
    """Pull advertiser data from the scraper's SQLite DB into a collection.

    This reads all advertisers (with their recon findings, social links,
    registry records, and warehouse votes), builds text representations,
    and feeds them through the standard ingestion pipeline.
    """
    try:
        from chatbot.connectors.scraper_connector import run_scraper_ingest

        result = await run_scraper_ingest(
            collection=body.collection,
            limit=body.limit,
        )
        return IngestFromScraperResponse(**result)
    except ImportError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Scraper connector not available: {exc}",
        ) from exc
    except Exception as exc:
        logger.exception("Scraper ingest failed.")
        raise HTTPException(
            status_code=500,
            detail=f"Scraper ingest failed: {exc}",
        ) from exc


# ------------------------------------------------------------------
# Chat
# ------------------------------------------------------------------


@router.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest) -> ChatResponse:
    """Ask a question against a named collection.

    The pipeline: embed question → retrieve relevant chunks → build
    prompt → generate answer with Phi-4-mini via Ollama → attach citations.
    """
    pipeline = _get_pipeline()

    # Build the where filter from metadata_filter if provided.
    where = None
    if body.metadata_filter:
        where = body.metadata_filter

    try:
        result = await pipeline.ask(
            collection=body.collection,
            question=body.question,
            top_k=body.top_k,
            where=where,
            temperature=body.temperature,
        )
    except Exception as exc:
        logger.exception("Chat query failed.")
        raise HTTPException(
            status_code=500,
            detail=f"Query failed: {exc}",
        ) from exc

    sources = [
        SourceCitation(
            doc_id=s["doc_id"],
            chunk_index=s["chunk_index"],
            excerpt=s["excerpt"],
            score=s["score"],
            metadata=s.get("metadata", {}),
        )
        for s in result["sources"]
    ]

    return ChatResponse(
        answer=result["answer"],
        sources=sources,
        collection=result["collection"],
        retrieved_count=result["retrieved_count"],
        elapsed_ms=result["elapsed_ms"],
    )


# ------------------------------------------------------------------
# Collections
# ------------------------------------------------------------------


@router.get("/collections", response_model=CollectionsResponse)
async def list_collections() -> CollectionsResponse:
    """List all available collections and their document counts."""
    ingestor = _get_ingestor()
    names = await ingestor.store.list_collections()
    infos: list[CollectionInfo] = []
    for name in names:
        count = await ingestor.store.collection_count(name)
        infos.append(CollectionInfo(name=name, document_count=count))
    return CollectionsResponse(collections=infos)


@router.delete("/collections/{name}")
async def delete_collection(name: str) -> dict:
    """Drop an entire collection."""
    ingestor = _get_ingestor()
    await ingestor.store.delete_collection(name)
    return {"status": "deleted", "collection": name}


# ------------------------------------------------------------------
# Health
# ------------------------------------------------------------------


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Health check: Ollama connectivity, model status, vector store stats."""
    pipeline = _get_pipeline()

    try:
        health_data = await pipeline.health_check()
    except Exception as exc:
        logger.exception("Health check failed.")
        return HealthResponse(
            status="error",
            llm_ok=False,
            model="unknown",
            collections=[],
            collection_counts={},
        )

    collections_list = health_data.get("collections", [])
    counts = health_data.get("collection_counts", {})

    if not health_data.get("llm_ok"):
        status = "degraded"
    elif not collections_list:
        status = "ok"  # LLM is fine, just no collections yet
    else:
        status = "ok"

    return HealthResponse(
        status=status,
        llm_ok=health_data.get("llm_ok", False),
        model=health_data.get("model", "unknown"),
        collections=collections_list,
        collection_counts=counts,
    )
