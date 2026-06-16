from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EmbedKeyCreate(BaseModel):
    label: str
    allowed_origins: str = ""


class EmbedKeyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    key: str
    label: str
    allowed_origins: str
    active: bool
    created_at: datetime
    last_used_at: datetime | None = None
