from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.database import get_db
from app.schemas import ChatRequest, ChatResponse
from app.services.echo_service import generate_echo_response

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ChatResponse:
    response = await generate_echo_response(db, settings, request.message)
    return ChatResponse(response=response)
