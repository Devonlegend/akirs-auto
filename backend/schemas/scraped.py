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
