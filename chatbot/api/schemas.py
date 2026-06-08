"""Pydantic request / response schemas for the chatbot API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ------------------------------------------------------------------
# Ingest
# ------------------------------------------------------------------


class IngestRequest(BaseModel):
    """Feed raw text into a named collection."""

    collection: str = Field(
        ...,
        min_length=1,
        max_length=128,
        pattern=r"^[a-zA-Z0-9_-]+$",
        description="Target collection name (alphanumeric, dash, underscore).",
    )
    text: str = Field(
        ...,
        min_length=1,
        description="Raw text content to ingest.",
    )
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Arbitrary key-value metadata to attach to all chunks.",
    )
    doc_id: str | None = Field(
        default=None,
        description="Optional external document ID. Auto-generated if omitted.",
    )


class IngestResponse(BaseModel):
    """Result of an ingest operation."""

    collection: str
    doc_id: str
    chunks_created: int
    elapsed_ms: float


class IngestFromScraperRequest(BaseModel):
    """Pull data from the scraper database into a collection."""

    collection: str = Field(
        default="akirs_businesses",
        description="Target collection name.",
    )
    limit: int | None = Field(
        default=None,
        ge=1,
        description="Optional max number of advertisers to ingest.",
    )


class IngestFromScraperResponse(BaseModel):
    """Result of a scraper ingest operation."""

    collection: str
    advertisers_processed: int
    chunks_created: int
    errors: list[str]
    elapsed_ms: float


# ------------------------------------------------------------------
# Chat
# ------------------------------------------------------------------


class ChatRequest(BaseModel):
    """Ask a question against a collection."""

    collection: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Which collection to query.",
    )
    question: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="The question to ask.",
    )
    top_k: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Number of chunks to retrieve.",
    )
    metadata_filter: dict[str, Any] | None = Field(
        default=None,
        description="Optional ChromaDB metadata filter (where clause).",
    )
    temperature: float | None = Field(
        default=None,
        ge=0.0,
        le=2.0,
        description="Optional LLM temperature override.",
    )


class SourceCitation(BaseModel):
    """A source citation for a chunk used in the answer."""

    doc_id: str
    chunk_index: int
    excerpt: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    """Response to a chat query."""

    answer: str
    sources: list[SourceCitation]
    collection: str
    retrieved_count: int
    elapsed_ms: float


# ------------------------------------------------------------------
# Collections
# ------------------------------------------------------------------


class CollectionInfo(BaseModel):
    """Info about a single collection."""

    name: str
    document_count: int


class CollectionsResponse(BaseModel):
    """List of all collections."""

    collections: list[CollectionInfo]


# ------------------------------------------------------------------
# Health
# ------------------------------------------------------------------


class HealthResponse(BaseModel):
    """Chatbot health status."""

    status: str  # "ok" | "degraded" | "error"
    llm_ok: bool
    model: str
    collections: list[str]
    collection_counts: dict[str, int]
    checked_at: datetime = Field(default_factory=datetime.utcnow)
