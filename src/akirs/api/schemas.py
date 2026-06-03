"""Pydantic request/response schemas for the FastAPI surface."""

from datetime import datetime

from pydantic import BaseModel, Field


class ScrapeJobRequest(BaseModel):
    locations: list[str] | None = Field(
        default=None,
        description="Akwa Ibom LGAs or town names. Defaults to all 31 LGAs if omitted.",
    )
    categories: list[str] | None = Field(
        default=None,
        description="Business category seeds. Defaults to the curated taxonomy.",
    )
    user_keywords: list[str] | None = Field(
        default=None,
        description="Extra free-form keywords to merge in.",
    )
    target_ads_per_keyword: int = Field(default=20, ge=1, le=500)
    use_llm_expansion: bool = Field(default=False)
    keyword_cap: int = Field(default=50, ge=1, le=2000)
    run_recon: bool = Field(default=True)
    country: str | None = Field(default=None, description="FB Ads country filter; defaults to settings value")


class JobCreatedResponse(BaseModel):
    job_id: int
    status: str
    celery_task_id: str | None = None


class JobStatusResponse(BaseModel):
    job_id: int
    kind: str
    status: str
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    error: str | None
    celery_task_id: str | None
    params: dict
    keyword_run_count: int
    ad_count: int
    advertiser_count: int


class SocialLinkOut(BaseModel):
    platform: str
    url: str


class AdvertiserOut(BaseModel):
    id: int
    name: str | None
    fb_url: str
    first_seen: datetime
    last_seen: datetime
    social_links: list[SocialLinkOut] = []


class ReconFindingOut(BaseModel):
    id: int
    source: str
    kind: str
    value: str
    confidence: float
    found_at: datetime


class GeographyOut(BaseModel):
    id: int
    name: str
    kind: str
    parent_id: int | None
