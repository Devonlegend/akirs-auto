"""Tests for the chatbot NLP cleaner and chunker (no heavy deps required)."""

from __future__ import annotations

from src.chatbot.nlp.chunker import Chunk, TextChunker
from src.chatbot.nlp.cleaner import clean_text, extract_sentences, is_noise


# ------------------------------------------------------------------
# Cleaner
# ------------------------------------------------------------------


def test_clean_text_collapses_whitespace():
    assert clean_text("hello    world\n\n  foo") == "hello world foo"


def test_clean_text_normalizes_smart_quotes():
    assert clean_text("“hello” ‘world’") == '"hello" \'world\''


def test_clean_text_strips_em_dash():
    assert clean_text("a—b") == "a--b"


def test_clean_text_empty():
    assert clean_text("") == ""
    assert clean_text("   \n\t  ") == ""


def test_clean_text_removes_zero_width():
    assert clean_text("foo​bar") == "foobar"


def test_is_noise_short_text():
    assert is_noise("hi") is True


def test_is_noise_normal_text():
    assert is_noise("This is a normal sentence with content.") is False


def test_is_noise_mostly_symbols():
    assert is_noise("!@#$%^&*()_+-=[]{}|;:,.<>?") is True


def test_extract_sentences():
    text = "Jane was born in Lagos. She studied CS. She founded a company."
    sentences = extract_sentences(text)
    assert len(sentences) == 3
    assert sentences[0] == "Jane was born in Lagos."


# ------------------------------------------------------------------
# Chunker
# ------------------------------------------------------------------


def test_chunker_short_text_single_chunk():
    chunker = TextChunker(chunk_size=512, chunk_overlap=64)
    chunks = chunker.chunk("This is a short piece of text.")
    assert len(chunks) == 1
    assert chunks[0].index == 0
    assert chunks[0].token_count > 0


def test_chunker_empty_text():
    chunker = TextChunker()
    assert chunker.chunk("") == []
    assert chunker.chunk("   ") == []


def test_chunker_assigns_sequential_indices():
    # Force small chunks so a long paragraph splits.
    chunker = TextChunker(chunk_size=10, chunk_overlap=2)
    long_text = " ".join(f"Sentence number {i} here." for i in range(20))
    chunks = chunker.chunk(long_text)
    assert len(chunks) > 1
    for i, c in enumerate(chunks):
        assert c.index == i


def test_chunker_splits_paragraphs():
    chunker = TextChunker(chunk_size=512, chunk_overlap=64)
    text = "First paragraph here.\n\nSecond paragraph here.\n\nThird paragraph."
    chunks = chunker.chunk(text)
    # Each small paragraph fits in one chunk, but they're separate paragraphs.
    assert len(chunks) >= 1


def test_chunker_count_tokens():
    chunker = TextChunker()
    count = chunker.count_tokens("hello world")
    assert count >= 1


def test_chunk_repr():
    c = Chunk(text="some text here", token_count=3, index=5)
    r = repr(c)
    assert "index=5" in r
    assert "tokens=3" in r
