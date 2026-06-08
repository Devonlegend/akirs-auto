"""Generic text cleaner — normalizes raw text before chunking and embedding."""

from __future__ import annotations

import re
import unicodedata


# Regex patterns compiled once at module level.
_MULTI_WHITESPACE = re.compile(r"\s+")
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")
# Zero-width and other invisible characters that add noise.
_INVISIBLE_CHARS = re.compile(r"[​‌‍‎‏  ﻿]")


def clean_text(text: str, *, strip_control_chars: bool = True) -> str:
    """Normalize *text* for embedding and storage.

    Steps applied (in order):

    1. Unicode normalization (NFC).
    2. Replace common smart quotes / dashes with ASCII equivalents.
    3. Strip zero-width and invisible characters.
    4. Optionally strip remaining ASCII control characters.
    5. Collapse all whitespace (including newlines) to a single space.
    6. Trim leading / trailing whitespace.

    Args:
        text: Raw input text.
        strip_control_chars: If ``True`` (default), remove ASCII control
            characters (except tab, newline which are collapsed anyway).

    Returns:
        Cleaned, normalized text string.
    """
    if not text:
        return ""

    # 1. Unicode normalization to composed form.
    text = unicodedata.normalize("NFC", text)

    # 2. Replace smart quotes, dashes, etc. with ASCII equivalents.
    text = _replace_typographic_chars(text)

    # 3. Strip zero-width / invisible characters.
    text = _INVISIBLE_CHARS.sub("", text)

    # 4. Strip control characters (optional).
    if strip_control_chars:
        text = _CONTROL_CHARS.sub("", text)

    # 5. Collapse whitespace.
    text = _MULTI_WHITESPACE.sub(" ", text)

    # 6. Trim.
    return text.strip()


def _replace_typographic_chars(text: str) -> str:
    """Replace common Unicode typographic characters with ASCII equivalents."""
    replacements: dict[int, str] = {
        0x201C: '"',   # left double quote
        0x201D: '"',   # right double quote
        0x201E: '"',   # double low-9 quote
        0x2018: "'",   # left single quote
        0x2019: "'",   # right single quote
        0x201A: "'",   # single low-9 quote
        0x2013: "-",   # en dash
        0x2014: "--",  # em dash
        0x2015: "--",  # horizontal bar
        0x2026: "...", # horizontal ellipsis
        0x00A0: " ",   # non-breaking space
        0x2022: "*",   # bullet
        0x2122: "(TM)",# trade mark sign
        0x00AE: "(R)", # registered sign
    }
    return text.translate(replacements)


def extract_sentences(text: str) -> list[str]:
    """Split *text* into a list of sentences.

    Uses a simple regex split on sentence-ending punctuation followed by
    whitespace + capital letter, plus handling for common abbreviations.
    This is intentionally lightweight — not a full NLP sentence segmenter.

    Args:
        text: Cleaned text (should already have gone through :func:`clean_text`).

    Returns:
        List of sentence strings (stripped, empty ones dropped).
    """
    if not text:
        return []

    # Simple sentence boundary: `. `, `! `, `? ` followed by a capital letter or end-of-string.
    # We split on the punctuation, keeping the punctuation with the preceding sentence.
    pattern = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")
    sentences = pattern.split(text)

    # Further split any remaining on newlines that remain.
    result: list[str] = []
    for sent in sentences:
        result.extend(s.strip() for s in sent.split("\n") if s.strip())

    return result


def is_noise(text: str, *, min_length: int = 10, min_alpha_ratio: float = 0.3) -> bool:
    """Heuristic to detect if *text* is likely noise / not useful content.

    Args:
        text: The cleaned text to check.
        min_length: Minimum character length to be considered content.
        min_alpha_ratio: Minimum ratio of alphabetic characters to total length.

    Returns:
        ``True`` if the text should be discarded as noise.
    """
    if len(text) < min_length:
        return True

    alpha_count = sum(1 for c in text if c.isalpha())
    if len(text) > 0 and (alpha_count / len(text)) < min_alpha_ratio:
        return True

    return False
