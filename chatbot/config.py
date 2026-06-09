"""Chatbot settings — pydantic-settings, loaded from environment / .env."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ChatbotSettings(BaseSettings):
    """Configuration for the RAG chatbot.

    All values can be overridden via environment variables prefixed with ``CHATBOT_``.
    """

    model_config = SettingsConfigDict(
        env_prefix="CHATBOT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # -- LLM / Ollama -------------------------------------------------------
    ollama_model: str = Field(
        default="phi4-mini",
        description="Ollama model name for Phi-4-mini.",
    )
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Ollama HTTP API base URL.",
    )
    llm_temperature: float = Field(
        default=0.3,
        ge=0.0,
        le=2.0,
        description="LLM temperature for generation.",
    )
    llm_max_tokens: int = Field(
        default=1024,
        ge=1,
        le=4096,
        description="Maximum tokens in the generated response.",
    )
    llm_timeout_seconds: float = Field(
        default=120.0,
        description="HTTP timeout for Ollama API calls.",
    )

    # -- Embeddings ---------------------------------------------------------
    embedding_model: str = Field(
        default="all-MiniLM-L6-v2",
        description="SentenceTransformer model name for embeddings.",
    )

    # -- Vector store -------------------------------------------------------
    vector_db_path: Path = Field(
        default=Path("chatbot_data/vector_db"),
        description="Directory for ChromaDB persistent storage.",
    )

    # -- Chunking -----------------------------------------------------------
    chunk_size: int = Field(
        default=512,
        ge=64,
        le=4096,
        description="Target chunk size in tokens.",
    )
    chunk_overlap: int = Field(
        default=64,
        ge=0,
        le=512,
        description="Overlap between consecutive chunks in tokens.",
    )

    # -- Retrieval ----------------------------------------------------------
    top_k: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Default number of chunks to retrieve per query.",
    )

    # -- Scraper DB ---------------------------------------------------------
    scraper_db_url: str = Field(
        default="sqlite+aiosqlite:///akirs.db",
        description="SQLAlchemy URL for the scraper's SQLite database.",
    )


# Module-level singleton — instantiated once, shared across the chatbot package.
settings = ChatbotSettings()
