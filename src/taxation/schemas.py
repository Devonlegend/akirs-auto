"""Pydantic schemas for the taxation agent's structured output."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TaxAssessment(BaseModel):
    """Structured taxability assessment produced by the LLM agent.

    The agent extracts a cleaned identity + contact profile and judges whether
    the entity is taxable. A record is treated as taxable when ``is_taxable`` is
    True — which the agent should only set when there is an identifiable entity,
    at least one contact channel, and some evidence of economic activity.
    """

    legal_name: str | None = Field(
        default=None, description="Best legal/business name for the entity."
    )
    entity_type: str | None = Field(
        default=None, description="'business' or 'individual' if determinable."
    )
    emails: list[str] = Field(default_factory=list, description="Extracted email addresses.")
    phones: list[str] = Field(default_factory=list, description="Extracted phone numbers.")
    address: str | None = Field(default=None, description="Best physical address, if any.")
    activity_signals: list[str] = Field(
        default_factory=list,
        description="Evidence of economic activity (active ads, registry, social following).",
    )
    is_taxable: bool = Field(
        default=False, description="True if the entity should be treated as taxable."
    )
    taxable_score: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Confidence in taxability, 0-1."
    )
    reasoning: str = Field(default="", description="Short justification for the decision.")
