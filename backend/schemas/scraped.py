from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, List, Dict, Any

class GeographyBase(BaseModel):
    name: str
    kind: str
    parent_id: Optional[int] = None

class GeographyCreate(GeographyBase):
    pass

class Geography(GeographyBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class AdvertiserBase(BaseModel):
    fb_url: str
    name: Optional[str] = None

class AdvertiserCreate(AdvertiserBase):
    pass

class Advertiser(AdvertiserBase):
    id: int
    first_seen: datetime
    last_seen: datetime
    model_config = ConfigDict(from_attributes=True)


class SocialLinkOut(BaseModel):
    platform: str
    url: str
    model_config = ConfigDict(from_attributes=True)


class AdvertiserEnriched(BaseModel):
    id: int
    name: Optional[str] = None
    fb_url: str
    first_seen: datetime
    last_seen: datetime
    platforms: List[str] = []          # distinct social link + profile platforms
    social_links: List[SocialLinkOut] = []
    emails: List[str] = []             # recon_findings where kind == "email"
    phones: List[str] = []             # recon_findings where kind == "phone"
    addresses: List[str] = []          # recon_findings where kind == "address"
    followers: Optional[int] = None    # max social_profiles.follower_count
    sources: List[str] = []            # distinct recon_findings.source


class AdBase(BaseModel):
    advertiser_id: int
    keyword_run_id: Optional[int] = None
    fb_ad_id: Optional[str] = None
    raw_json: Dict[str, Any] = {}

class AdCreate(AdBase):
    pass

class Ad(AdBase):
    id: int
    scraped_at: datetime
    model_config = ConfigDict(from_attributes=True)
