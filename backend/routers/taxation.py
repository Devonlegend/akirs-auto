"""Taxation API — trigger LLM classification and list taxable entities."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from src.db.models import TaxableEntity
from taxation.processor import run_tax_classification

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/taxation", tags=["Taxation"])
DbDep = Annotated[AsyncSession, Depends(get_db)]


class ProcessRequest(BaseModel):
    limit: int | None = None
    advertiser_ids: list[int] | None = None


class ProcessResponse(BaseModel):
    processed: int
    taxable: int
    errors: list[str]
    elapsed_ms: float


class TaxableEntityOut(BaseModel):
    advertiser_id: int
    legal_name: str | None
    entity_type: str | None
    emails: str | None
    phones: str | None
    address: str | None
    taxable_score: float
    reasoning: str | None
    model: str | None


@router.post("/process", response_model=ProcessResponse)
async def process(body: ProcessRequest) -> ProcessResponse:
    """Run the taxable-entity classifier over advertisers."""
    try:
        summary = await run_tax_classification(
            limit=body.limit, advertiser_ids=body.advertiser_ids
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Taxation processing failed.")
        raise HTTPException(status_code=500, detail=f"Processing failed: {exc}") from exc
    return ProcessResponse(**summary)


@router.get("/entities", response_model=list[TaxableEntityOut])
async def list_entities(db: DbDep, limit: int = 1000) -> list[TaxableEntityOut]:
    """List persisted taxable entities."""
    result = await db.execute(select(TaxableEntity).limit(limit))
    entities = result.scalars().all()
    return [
        TaxableEntityOut(
            advertiser_id=e.advertiser_id,
            legal_name=e.legal_name,
            entity_type=e.entity_type,
            emails=e.emails,
            phones=e.phones,
            address=e.address,
            taxable_score=e.taxable_score,
            reasoning=e.reasoning,
            model=e.model,
        )
        for e in entities
    ]
