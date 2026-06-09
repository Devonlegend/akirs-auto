"""Abstract LLM backend interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class LLMResponse:
    """Response from an LLM backend."""

    content: str
    model: str = ""
    total_tokens: int = 0
    metadata: dict = field(default_factory=dict)


class LLMBackend(ABC):
    """Abstract interface for a language model backend.

    Implementations handle the specifics of calling a particular LLM
    (Ollama, OpenAI-compatible API, etc.).
    """

    @abstractmethod
    async def generate(
        self,
        system_prompt: str,
        context: str,
        question: str,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """Generate an answer given a system prompt, retrieved context, and user question.

        Args:
            system_prompt: The system-level instruction for the model.
            context: The retrieved context chunks (already concatenated).
            question: The user's question.
            temperature: Optional override for temperature.
            max_tokens: Optional override for max output tokens.

        Returns:
            An :class:`LLMResponse` with the model's answer.
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Return ``True`` if the backend is reachable and the model is loaded."""
        ...
