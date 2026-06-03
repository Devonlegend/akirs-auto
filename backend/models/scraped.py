from datetime import datetime
from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class Geography(Base):
    __tablename__ = "geographies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("geographies.id"), nullable=True)

    parent: Mapped["Geography | None"] = relationship("Geography", remote_side="Geography.id")

    __table_args__ = (UniqueConstraint("name", "kind", name="uq_geography_name_kind"),)


class ScrapeJob(Base):
    __tablename__ = "scrape_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued")
    params_json: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    keyword_runs: Mapped[list["KeywordRun"]] = relationship(
        "KeywordRun", back_populates="scrape_job", cascade="all, delete-orphan"
    )


class KeywordRun(Base):
    __tablename__ = "keyword_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scrape_job_id: Mapped[int] = mapped_column(ForeignKey("scrape_jobs.id"), nullable=False, index=True)
    keyword: Mapped[str] = mapped_column(String(256), nullable=False)
    location_geography_id: Mapped[int | None] = mapped_column(ForeignKey("geographies.id"), nullable=True)
    ads_found: Mapped[int] = mapped_column(Integer, default=0)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    scrape_job: Mapped[ScrapeJob] = relationship("ScrapeJob", back_populates="keyword_runs")
    ads: Mapped[list["Ad"]] = relationship("Ad", back_populates="keyword_run")


class Advertiser(Base):
    __tablename__ = "advertisers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fb_url: Mapped[str] = mapped_column(String(512), nullable=False, unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_seen: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    ads: Mapped[list["Ad"]] = relationship("Ad", back_populates="advertiser")
    social_links: Mapped[list["SocialLink"]] = relationship(
        "SocialLink", back_populates="advertiser", cascade="all, delete-orphan"
    )
    recon_findings: Mapped[list["ReconFinding"]] = relationship(
        "ReconFinding", back_populates="advertiser", cascade="all, delete-orphan"
    )
    social_profiles: Mapped[list["SocialProfile"]] = relationship(
        "SocialProfile", back_populates="advertiser", cascade="all, delete-orphan"
    )
    registry_records: Mapped[list["RegistryRecord"]] = relationship(
        "RegistryRecord", back_populates="advertiser", cascade="all, delete-orphan"
    )


class Ad(Base):
    __tablename__ = "ads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    advertiser_id: Mapped[int] = mapped_column(ForeignKey("advertisers.id"), nullable=False, index=True)
    keyword_run_id: Mapped[int | None] = mapped_column(ForeignKey("keyword_runs.id"), nullable=True)
    fb_ad_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    raw_json: Mapped[dict] = mapped_column(JSON, default=dict)
    scraped_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    advertiser: Mapped[Advertiser] = relationship("Advertiser", back_populates="ads")
    keyword_run: Mapped[KeywordRun | None] = relationship("KeywordRun", back_populates="ads")


class SocialLink(Base):
    __tablename__ = "social_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    advertiser_id: Mapped[int] = mapped_column(ForeignKey("advertisers.id"), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    url: Mapped[str] = mapped_column(String(1024), nullable=False)

    advertiser: Mapped[Advertiser] = relationship("Advertiser", back_populates="social_links")

    __table_args__ = (UniqueConstraint("advertiser_id", "url", name="uq_social_link_adv_url"),)


class ReconFinding(Base):
    __tablename__ = "recon_findings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    advertiser_id: Mapped[int] = mapped_column(ForeignKey("advertisers.id"), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    raw_json: Mapped[dict] = mapped_column(JSON, default=dict)
    found_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    advertiser: Mapped[Advertiser] = relationship("Advertiser", back_populates="recon_findings")


class SocialProfile(Base):
    __tablename__ = "social_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    advertiser_id: Mapped[int] = mapped_column(ForeignKey("advertisers.id"), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    handle: Mapped[str | None] = mapped_column(String(256), nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    follower_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_json: Mapped[dict] = mapped_column(JSON, default=dict)
    scraped_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    advertiser: Mapped[Advertiser] = relationship("Advertiser", back_populates="social_profiles")

    __table_args__ = (UniqueConstraint("advertiser_id", "platform", "handle", name="uq_social_profile"),)


class RegistryRecord(Base):
    __tablename__ = "registry_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    advertiser_id: Mapped[int] = mapped_column(ForeignKey("advertisers.id"), nullable=False, index=True)
    registry: Mapped[str] = mapped_column(String(64), nullable=False)
    registration_number: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    raw_json: Mapped[dict] = mapped_column(JSON, default=dict)
    found_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    advertiser: Mapped[Advertiser] = relationship("Advertiser", back_populates="registry_records")
