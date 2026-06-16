from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.schemas.auth import LoginRequest, LoginResponse
from backend.security import make_token
from backend.services.auth_queries import authenticate_user

router = APIRouter(prefix="/auth", tags=["Auth"])
DbDep = Annotated[AsyncSession, Depends(get_db)]


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, db: DbDep) -> LoginResponse:
    user = await authenticate_user(db, body.username.strip(), body.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return LoginResponse(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        account_type=user.account_type.value,
        token=make_token(user.id, user.username, user.account_type.value),
    )
