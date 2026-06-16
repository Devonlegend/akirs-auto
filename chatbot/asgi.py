from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from chatbot.api.routes import prepare_pipeline, shutdown_pipeline
from chatbot.api.routes import router as chatbot_router
from backend.database import get_db
from backend.models.embed import EmbedKey
from sqlalchemy import select

@asynccontextmanager
async def lifespan(app: FastAPI):
    await prepare_pipeline()
    yield
    await shutdown_pipeline()

app = FastAPI(title="Akirs Chatbot App", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In a real app we'd scope this to allowed_origins of the embed key
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

from datetime import datetime

async def verify_embed_key(
    x_embed_key: str = Header(..., description="The embed key for the widget"),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(EmbedKey).where(EmbedKey.key == x_embed_key))
    key_obj = result.scalar_one_or_none()
    if not key_obj or not key_obj.active:
        raise HTTPException(status_code=401, detail="Invalid or inactive embed key")
    
    # Update last used
    key_obj.last_used_at = datetime.utcnow()
    await db.commit()

app.include_router(chatbot_router, dependencies=[Depends(verify_embed_key)])
