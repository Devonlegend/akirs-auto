"""Taxation — LLM-driven taxable-entity classification of scraped advertisers.

Reads each scraped advertiser, uses a pydantic-ai agent (local Ollama phi4-mini)
to extract a clean structured profile and judge taxability, and persists the
taxable ones to the ``taxable_entities`` table.
"""

from taxation.schemas import TaxAssessment

__all__ = ["TaxAssessment"]
