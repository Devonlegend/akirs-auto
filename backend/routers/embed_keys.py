from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.embed import EmbedKey
from backend.models.users import Admin
from backend.schemas.embed import EmbedKeyCreate, EmbedKeyOut
from backend.security import verify_token
from backend.services.embed_keys import create_embed_key

router = APIRouter(prefix="/embed-keys", tags=["Embed Keys"])
DbDep = Annotated[AsyncSession, Depends(get_db)]


async def require_admin(
    db: DbDep,
    authorization: Annotated[str | None, Header()] = None,
) -> Admin:
    token = authorization.removeprefix("Bearer ").strip() if authorization else None
    payload = verify_token(token)
    if payload is None or payload.get("account_type") != "Admin":
        raise HTTPException(status_code=401, detail="Admin authentication required")
    admin = await db.get(Admin, payload["uid"])
    if admin is None or not admin.can_manage_embed_keys:
        raise HTTPException(status_code=403, detail="Not allowed to manage embed keys")
    return admin


AdminDep = Annotated[Admin, Depends(require_admin)]


@router.get("", response_model=list[EmbedKeyOut])
async def list_embed_keys(db: DbDep, _admin: AdminDep) -> list[EmbedKey]:
    result = await db.execute(select(EmbedKey).order_by(EmbedKey.created_at.desc()))
    return list(result.scalars().all())


@router.post("", response_model=EmbedKeyOut, status_code=201)
async def create_key(body: EmbedKeyCreate, db: DbDep, admin: AdminDep) -> EmbedKey:
    return await create_embed_key(
        db,
        label=body.label.strip() or "Untitled",
        allowed_origins=body.allowed_origins.strip(),
        owner_id=admin.id,
    )
