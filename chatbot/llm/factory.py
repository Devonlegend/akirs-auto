"""Factory that builds the configured LLM backend."""

from __future__ import annotations

from chatbot.config import settings
from chatbot.llm.base import LLMBackend


def build_llm_backend() -> LLMBackend:
    """Instantiate the LLM backend selected by ``settings.llm_backend``.

    - ``ollama``: local dev default — auto-starts/pulls the model.
    - ``llamacpp``: production CPU serving via llama.cpp ``llama-server``.
    """
    if settings.llm_backend == "llamacpp":
        from chatbot.llm.llamacpp_backend import LlamaCppBackend

        return LlamaCppBackend()

    from chatbot.llm.ollama_backend import OllamaBackend

    return OllamaBackend()
