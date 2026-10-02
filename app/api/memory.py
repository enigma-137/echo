from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.memory.manager import MemoryManager
from app.schemas import MemoryCreate, MemoryResponse, MemoryUpdate
from app.services.profile import ProfileService

router = APIRouter(tags=["memory"])


@router.post("/memory", response_model=MemoryResponse)
async def create_memory(payload: MemoryCreate, db: AsyncSession = Depends(get_db)) -> MemoryResponse:
    manager = MemoryManager(db)
    user = await manager.get_or_create_default_user()
    memory = await manager.store_memory(user.id, payload.content, payload.kind, payload.tags)
    return MemoryResponse.model_validate(memory)


@router.get("/memory", response_model=list[MemoryResponse])
async def list_memories(db: AsyncSession = Depends(get_db)) -> list[MemoryResponse]:
    manager = MemoryManager(db)
    user = await manager.get_or_create_default_user()
    memories = await manager.list_memories(user.id)
    return [MemoryResponse.model_validate(memory) for memory in memories]


@router.patch("/memory/{memory_id}", response_model=MemoryResponse)
async def update_memory(
    memory_id: int,
    payload: MemoryUpdate,
    db: AsyncSession = Depends(get_db),
) -> MemoryResponse:
    manager = MemoryManager(db)
    user = await manager.get_or_create_default_user()
    memory = await manager.update_memory(user.id, memory_id, payload.content, payload.tags)
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
    return MemoryResponse.model_validate(memory)


@router.delete("/memory/{memory_id}")
async def delete_memory(memory_id: int, db: AsyncSession = Depends(get_db)) -> dict[str, bool]:
    manager = MemoryManager(db)
    user = await manager.get_or_create_default_user()
    deleted = await manager.delete_memory(user.id, memory_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"deleted": True}


@router.get("/profile")
async def get_profile(db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    manager = MemoryManager(db)
    user = await manager.get_or_create_default_user()
    profile_service = ProfileService(db)
    return await profile_service.get_or_create_profile(user)


@router.patch("/profile")
async def patch_profile(updates: dict[str, object], db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    manager = MemoryManager(db)
    user = await manager.get_or_create_default_user()
    profile_service = ProfileService(db)
    return await profile_service.update_profile(user.id, updates)
