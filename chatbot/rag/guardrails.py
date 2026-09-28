"""Scope and safety guardrails for the AKIRS assistant.

These checks are deterministic and cheap. They run before retrieval and before
the LLM so that harmful or clearly conversational inputs get an instant, scoped
reply instead of a slow (and potentially unsafe) generation.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Harmful intent
#
# Deliberately narrow. Legitimate tax vocabulary such as "penalty",
# "enforcement", "evasion", "seizure", or "audit" is intentionally NOT listed
# so real tax questions are never misclassified.
# ---------------------------------------------------------------------------
_UNSAFE_PATTERNS = (
    r"\b(kill|murder|assassinate|shoot|stab|poison|strangle|behead|kidnap|abduct)\b",
    r"\b(hurt|harm|attack|beat\s+up|maim)\s+"
    r"(someone|somebody|him|her|them|people|a\s+person|my\s+\w+)\b",
    r"\bhow\s+to\s+(hurt|harm|attack|beat\s+up|kidnap|poison)\b",
    r"\b(make|build|assemble|construct)\s+(a\s+|an\s+)?"
    r"(bomb|explosive|pipe\s+bomb|gun|weapon|silencer)\b",
    r"\b(terrorist|terrorism|mass\s+shooting)\b",
    r"\bsuicid",
    r"\bself[\s-]?harm\b",
    r"\b(kill|hurt)\s+(my\s?self|me)\b",
    r"\b(make|cook|synthesize|produce)\s+"
    r"(meth|methamphetamine|cocaine|heroin|fentanyl)\b",
    r"\b(hack|ddos|phish|malware|ransomware|keylogger)\b",
    r"\bsteal\s+(a\s+|the\s+)?(password|identity|credit\s+card|card\s+details)\b",
)
_UNSAFE_RE = re.compile("|".join(_UNSAFE_PATTERNS), re.IGNORECASE)

# Greetings / identity questions must be the *entire* message, so a real
# question that merely starts with "hello" (e.g. "hello, how do I file PAYE?")
# is not swallowed by the conversational fast-path.
_GREETING_RE = re.compile(
    r"^(hi|hello|hey|yo|good\s*(morning|afternoon|evening)"
    r"|what\s+can\s+you\s+do|who\s+are\s+you|how\s+are\s+you)"
    r"[\s!.,?]*$",
    re.IGNORECASE,
)

_THANKS_RE = re.compile(r"^(thanks|thank\s+you|thx|cheers)[\s!.,?]*$", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Canned replies
# ---------------------------------------------------------------------------
UNSAFE_REPLY = (
    "I'm the AKIRS tax assistant, so I can't help with that. If you or someone "
    "else is in immediate danger, please call the Nigerian emergency number 112. "
    "I can help with Akwa Ibom State tax matters such as PAYE, Withholding Tax, "
    "AISTIN registration, annual returns, and Tax Clearance Certificates."
)

SCOPE_REPLY = (
    "I can only help with Akwa Ibom State tax matters, and I couldn't find "
    "information about that in the AKIRS knowledge base. Please rephrase your "
    "tax question, for example about PAYE, Withholding Tax, AISTIN, annual "
    "returns, or TCC, or contact AKIRS directly for an authoritative answer."
)

GREETING_REPLY = (
    "Hello! I'm the AKIRS Assistant for the Akwa Ibom State Internal Revenue "
    "Service. I can help with PAYE, Withholding Tax, AISTIN registration, "
    "annual returns, Tax Clearance Certificates, and other state tax matters. "
    "What would you like to know?"
)

THANKS_REPLY = (
    "You're welcome. If you have another Akwa Ibom State tax question, I'm "
    "here to help."
)


def is_unsafe(question: str) -> bool:
    """True if the message clearly requests harm or illegal activity."""
    return bool(_UNSAFE_RE.search(question or ""))


def is_greeting(question: str) -> bool:
    """True for a pure greeting / identity message that skips retrieval."""
    q = (question or "").strip()
    if not q or len(q.split()) > 12:
        return False
    return bool(_GREETING_RE.match(q))


def is_thanks(question: str) -> bool:
    """True for a pure expression of thanks."""
    q = (question or "").strip()
    if not q or len(q.split()) > 6:
        return False
    return bool(_THANKS_RE.match(q))


def canned_reply(question: str) -> str | None:
    """Return an instant scoped reply for unsafe/greeting/thanks inputs.

    Returns ``None`` when the message should go through the normal RAG flow.
    """
    q = (question or "").strip()
    if not q:
        return None
    if is_unsafe(q):
        return UNSAFE_REPLY
    if is_thanks(q):
        return THANKS_REPLY
    if is_greeting(q):
        return GREETING_REPLY
    return None
