"""Tests for the text cleaner — especially that word spacing is preserved.

A prior edit widened the invisible-character class to include a literal space,
which stripped every word boundary from all ingested text and wrecked retrieval
quality. These tests lock the behaviour down.
"""

from __future__ import annotations

from chatbot.nlp.cleaner import clean_text


def test_single_spaces_are_preserved():
    text = "A taxpayer who disposes of a chargeable asset should report the gain."
    assert clean_text(text) == text


def test_runs_of_whitespace_collapse_to_one_space():
    assert clean_text("hello    world") == "hello world"
    assert clean_text("a\t\tb") == "a b"


def test_zero_width_and_bom_chars_are_removed_without_touching_spaces():
    assert clean_text("hel\u200blo wo\u200crld\ufeff") == "hello world"


def test_real_words_are_never_concatenated():
    # Guard against the regression where clean_text returned "Ataxpayerwho...".
    out = clean_text("PAYE is remitted monthly by the employer.")
    assert " " in out
    assert "PAYE is remitted monthly" in out
