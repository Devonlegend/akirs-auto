"""Generic text chunker using tiktoken for accurate token counting.

Produces overlapping chunks suitable for embedding and semantic retrieval.
No domain-specific logic — works with any text.
"""

from __future__ import annotations

import re

import tiktoken

from chatbot.config import settings

# Paragraph / sentence boundary patterns used for "soft" split points.
_PARAGRAPH_BREAK = re.compile(r"\n\s*\n")  # blank line
_SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")


def _default_tokenizer() -> tiktoken.Encoding:
    """Return the default tiktoken encoding (cl100k_base — GPT-4 / embedding-friendly)."""
    return tiktoken.get_encoding("cl100k_base")


class TextChunker:
    """Splits arbitrary text into overlapping chunks of *roughly* ``chunk_size`` tokens.

    Chunking strategy:

    1. Try to split on paragraph boundaries first.
    2. Within a paragraph, try sentence boundaries.
    3. If a single sentence exceeds ``chunk_size``, fall back to a fixed-size
       sliding window with ``chunk_overlap`` tokens of overlap.

    Usage::

        chunker = TextChunker()
        chunks = chunker.chunk("very long text ...")
        for chunk in chunks:
            print(chunk.text, chunk.token_count)
    """

    def __init__(
        self,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
        encoding: tiktoken.Encoding | None = None,
    ) -> None:
        self._chunk_size = chunk_size if chunk_size is not None else settings.chunk_size
        self._chunk_overlap = chunk_overlap if chunk_overlap is not None else settings.chunk_overlap
        self._enc = encoding if encoding is not None else _default_tokenizer()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def chunk(self, text: str) -> list[Chunk]:
        """Split *text* into a list of :class:`Chunk` objects.

        Args:
            text: The (cleaned) text to chunk.

        Returns:
            List of chunks.  May be empty if *text* is empty.
        """
        if not text.strip():
            return []

        paragraphs = self._split_paragraphs(text)
        chunks: list[Chunk] = []

        for para in paragraphs:
            para_tokens = self._token_count(para)
            if para_tokens <= self._chunk_size:
                if para_tokens > 0:
                    chunks.append(Chunk(text=para, token_count=para_tokens))
            else:
                # Paragraph too large — split further.
                chunks.extend(self._chunk_paragraph(para))

        # Assign sequential chunk indices.
        for i, c in enumerate(chunks):
            c.index = i

        return chunks

    def count_tokens(self, text: str) -> int:
        """Return the number of tokens in *text*."""
        return self._token_count(text)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _token_count(self, text: str) -> int:
        return len(self._enc.encode(text))

    @staticmethod
    def _split_paragraphs(text: str) -> list[str]:
        """Split text on blank lines, keeping non-empty paragraphs."""
        parts = _PARAGRAPH_BREAK.split(text.strip())
        return [p.strip() for p in parts if p.strip()]

    def _chunk_paragraph(self, paragraph: str) -> list[Chunk]:
        """Split an oversized paragraph into smaller chunks."""
        sentences = self._split_sentences(paragraph)

        chunks: list[Chunk] = []
        current_parts: list[str] = []
        current_len = 0

        for sent in sentences:
            sent_len = self._token_count(sent)

            # If a single sentence is bigger than chunk_size, we must
            # split it with a sliding window.
            if sent_len > self._chunk_size:
                # Flush whatever we have accumulated first.
                if current_parts:
                    chunks.append(self._build_chunk(current_parts))
                    current_parts = []
                    current_len = 0
                chunks.extend(self._sliding_window(sent))
                continue

            # If adding this sentence would overflow, flush and start a new chunk.
            if current_len + sent_len > self._chunk_size and current_parts:
                chunks.append(self._build_chunk(current_parts))
                # Start new chunk with overlap: carry over the last sentence
                # if it fits as overlap context.
                overlap_sent = current_parts[-1] if current_parts else ""
                overlap_len = self._token_count(overlap_sent)
                current_parts = [overlap_sent] if overlap_len < self._chunk_overlap * 2 else []
                current_len = overlap_len if current_parts else 0

            current_parts.append(sent)
            current_len += sent_len

        # Flush remaining.
        if current_parts:
            chunks.append(self._build_chunk(current_parts))

        return chunks

    @staticmethod
    def _split_sentences(paragraph: str) -> list[str]:
        """Split a paragraph into sentences, keeping the punctuation attached."""
        # First try sentence-break regex.
        parts = _SENTENCE_BREAK.split(paragraph)
        # Re-attach the punctuation that was consumed by the lookbehind.
        result: list[str] = []
        for i, part in enumerate(parts):
            part = part.strip()
            if not part:
                continue
            # If the part doesn't end with sentence-ending punctuation and
            # there's a next part, the regex consumed it — add a period.
            if i < len(parts) - 1 and not part[-1] in ".!?":
                part += "."
            result.append(part)
        return result

    def _sliding_window(self, text: str) -> list[Chunk]:
        """Create chunks from a single long text using a sliding window."""
        tokens = self._enc.encode(text)
        chunks: list[Chunk] = []
        step = max(1, self._chunk_size - self._chunk_overlap)

        start = 0
        while start < len(tokens):
            window = tokens[start : start + self._chunk_size]
            chunk_text = self._enc.decode(window)
            chunks.append(Chunk(text=chunk_text, token_count=len(window)))
            if start + self._chunk_size >= len(tokens):
                break
            start += step

        return chunks

    def _build_chunk(self, parts: list[str]) -> Chunk:
        text = " ".join(parts)
        return Chunk(text=text, token_count=self._token_count(text))


# ------------------------------------------------------------------
# Chunk data class
# ------------------------------------------------------------------


class Chunk:
    """A single text chunk produced by :class:`TextChunker`.

    Attributes:
        text: The chunk text.
        token_count: Number of tokens in the chunk.
        index: Zero-based position within the parent document (set by the chunker).
    """

    __slots__ = ("text", "token_count", "index")

    def __init__(self, text: str, token_count: int, index: int = -1) -> None:
        self.text = text
        self.token_count = token_count
        self.index = index

    def __repr__(self) -> str:
        return f"Chunk(index={self.index}, tokens={self.token_count}, text={self.text[:60]!r}...)"
