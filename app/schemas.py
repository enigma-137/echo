from datetime import datetime

from pydantic import BaseModel, Field

from app.models.memory import MemoryKind


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)


class ChatResponse(BaseModel):
    response: str


class MemoryCreate(BaseModel):
    content: str = Field(..., min_length=1)
    kind: MemoryKind = MemoryKind.LONG_TERM
    tags: str | None = None


class MemoryUpdate(BaseModel):
    content: str = Field(..., min_length=1)
    tags: str | None = None


class MemoryResponse(BaseModel):
    id: int
    kind: MemoryKind
    content: str
    tags: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class HealthResponse(BaseModel):
    status: str
    app: str
    environment: str
    voice: dict[str, object] | None = None
