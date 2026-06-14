"""Pydantic-AI agent for taxable-entity assessment via local Ollama phi4-mini."""

from __future__ import annotations

import logging
from functools import lru_cache

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider

from src.config.settings import get_settings
from .schemas import TaxAssessment

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a tax-registration analyst for a Nigerian state revenue service. You are \
given a raw data profile scraped about a business or individual that advertises \
online. Produce a single structured assessment.

Do three things in one pass:
1. EXTRACT IDENTITY — the best legal/business name and whether it is a 'business' \
or an 'individual'.
2. EXTRACT CONTACT — emails, phone numbers, and the best physical address. A \
taxpayer must be reachable and identifiable.
3. ASSESS ECONOMIC ACTIVITY — note signals such as active ads, a company registry \
record, or a meaningful social following.

Decide taxability:
- Set is_taxable = true ONLY when there is (a) an identifiable entity, (b) at \
least one contact channel (email, phone, or address), AND (c) some evidence of \
economic activity.
- Set taxable_score between 0 and 1 reflecting your confidence.
- Give a short reasoning. Use ONLY the provided data; do not invent contacts.
"""


@lru_cache(maxsize=1)
def get_agent() -> Agent[None, TaxAssessment]:
    """Build (once) the pydantic-ai agent bound to Ollama's OpenAI-compatible API."""
    settings = get_settings()
    base_url = settings.ollama_base_url.rstrip("/") + "/v1"
    model = OpenAIModel(
        settings.tax_model,
        provider=OpenAIProvider(base_url=base_url, api_key="ollama"),
    )
    return Agent(
        model,
        output_type=TaxAssessment,
        system_prompt=SYSTEM_PROMPT,
        retries=2,
    )


async def assess(blob: str) -> TaxAssessment:
    """Run the agent over a profile *blob* and return a structured assessment."""
    agent = get_agent()
    result = await agent.run(blob)
    return result.output
