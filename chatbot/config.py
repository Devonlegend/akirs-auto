"""Chatbot settings — pydantic-settings, loaded from environment / .env."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

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

    # -- Feature toggle -----------------------------------------------------
    enabled: bool = Field(
        default=True,
        description="Master switch for the chatbot. When false, the backend "
        "never imports the RAG stack, warms the LLM, ingests the knowledge "
        "base, or mounts any chatbot route/widget.",
    )

    # -- LLM backend selection ---------------------------------------------
    llm_backend: Literal["ollama", "llamacpp"] = Field(
        default="ollama",
        description="Which LLM backend serves generation. 'ollama' for local "
        "dev, 'llamacpp' for production CPU serving via llama.cpp "
        "llama-server (OpenAI-compatible API).",
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
        default=512,
        ge=1,
        le=4096,
        description="Maximum tokens in the generated response. AKIRS answers "
        "usually need ~180-350 tokens; 1024 wastes ~3x decode time.",
    )
    llm_timeout_seconds: float = Field(
        default=120.0,
        description="HTTP timeout for Ollama API calls.",
    )
    ollama_keep_alive: str = Field(
        default="10m",
        description="How long Ollama keeps the model in memory (avoids reload "
        "per request, which costs seconds of load_duration).",
    )
    ollama_num_ctx: int = Field(
        default=2048,
        ge=512,
        le=32768,
        description="Context window (tokens) given to Ollama per request.",
    )

    # -- LLM / llama.cpp ------------------------------------------------------
    llamacpp_base_url: str = Field(
        default="http://localhost:8080",
        description="llama.cpp llama-server HTTP base URL (OpenAI-compatible).",
    )
    llamacpp_model: str = Field(
        default="gemma-3-1b",
        description="Model label reported by the llama.cpp backend in logs and "
        "health checks (llama.cpp serves a single preloaded model).",
    )
    llamacpp_api_key: str = Field(
        default="",
        description="Optional Bearer token sent to llama-server when it is run "
        "with --api-key. Empty means no Authorization header is sent.",
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
        default=8,
        ge=1,
        le=50,
        description="Default number of chunks to retrieve per query. 8 gives a "
        "small model a better chance that the chunk actually answering a broad "
        "question (e.g. 'how do I pay my tax') lands in the context window; "
        "prompt_eval scales linearly so more chunks = slower first token.",
    )
    relevance_threshold: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Minimum chunk score (1 - cosine_distance) to count as relevant context.",
    )
    context_max_tokens: int = Field(
        default=2000,
        ge=200,
        le=8000,
        description="Approximate token budget for the assembled retrieval "
        "context passed to the LLM. Too small and the highest-value chunk "
        "(e.g. the payment steps for 'how do I pay my tax') is dropped even "
        "when retrieved; too large and a small model's context window fills "
        "with noise and the first token slows.",
    )

    # -- Knowledge base -----------------------------------------------------
    knowledge_collection: str = Field(
        default="akirs_tax",
        description="Collection name for the AKIRS tax knowledge base.",
    )
    knowledge_dir: Path = Field(
        default=Path("chatbot/knowledge"),
        description="Folder of markdown files auto-ingested into the KB at startup.",
    )

    # -- Scraper DB ---------------------------------------------------------
    scraper_db_url: str = Field(
        default="sqlite+aiosqlite:///akirs.db",
        description="SQLAlchemy URL for the scraper's SQLite database.",
    )


# Module-level singleton — instantiated once, shared across the chatbot package.
settings = ChatbotSettings()
