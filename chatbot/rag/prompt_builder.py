"""Prompt builder — formats system + context + question for Phi-4-mini."""

from __future__ import annotations

DEFAULT_SYSTEM_PROMPT = """\
You are a helpful, accurate assistant. Answer the user's question using ONLY \
the provided context below. Follow these rules strictly:

1. If the answer IS found in the context, provide a clear, concise answer \
and cite which source(s) you used (by doc_id or chunk index).
2. If the answer is NOT found in the context, say: "I don't have enough \
information in the provided context to answer that."
3. Do NOT use any outside knowledge — rely exclusively on the context.
4. If the context contains conflicting information, point that out.
5. Keep answers concise but complete."""


GENERAL_SYSTEM_PROMPT = """\
You are the Akirs assistant — a helpful, friendly chatbot. The user's question \
did not match anything in the knowledge base, so answer it conversationally \
from your own general knowledge.

1. Respond naturally to greetings, small talk, and simple general questions.
2. Keep answers brief and clear.
3. If the question seems to be asking about specific Akirs business/advertiser \
data that you don't have, say you don't have that on hand and suggest they \
rephrase or ingest the relevant data."""


def build_prompt(
    question: str,
    context: str,
    *,
    system_prompt: str | None = None,
) -> tuple[str, str]:
    """Build the system + user prompts for the RAG pipeline.

    Args:
        question: The user's question.
        context: The formatted context string (from :func:`retrieval.retriever.format_context`).
        system_prompt: Optional override for the system prompt.

    Returns:
        A tuple of ``(system_prompt, user_prompt)``.
    """
    system = system_prompt if system_prompt is not None else DEFAULT_SYSTEM_PROMPT
    return system, context
