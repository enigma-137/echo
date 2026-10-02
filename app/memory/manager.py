import math
from typing import Optional

from sqlalchemy import Select, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.memory import Memory, MemoryKind
from app.models.user import User


DEFAULT_USER_EXTERNAL_ID = "default"


def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    """Compute cosine similarity between two float vectors."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    norm_a = math.sqrt(sum(a * a for a in v1))
    norm_b = math.sqrt(sum(b * b for b in v2))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class MemoryManager:
    """Owns persistence, semantic vector search, and retrieval of Echo memories."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_or_create_default_user(self) -> User:
        result = await self.db.execute(select(User).where(User.external_id == DEFAULT_USER_EXTERNAL_ID))
        user = result.scalar_one_or_none()
        if user:
            return user

        user = User(
            name="User",
            preferred_name="Friend",
            external_id=DEFAULT_USER_EXTERNAL_ID,
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def list_memories(
        self,
        user_id: int,
        kind: MemoryKind | None = None,
        limit: int = 50,
    ) -> list[Memory]:
        query: Select[tuple[Memory]] = select(Memory).where(Memory.user_id == user_id)
        if kind:
            query = query.where(Memory.kind == kind)
        query = query.order_by(Memory.updated_at.desc()).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def search_memories(self, user_id: int, query: str, limit: int = 10) -> list[Memory]:
        """Keyword / pattern search across memory content and tags."""
        pattern = f"%{query}%"
        result = await self.db.execute(
            select(Memory)
            .where(Memory.user_id == user_id)
            .where(or_(Memory.content.ilike(pattern), Memory.tags.ilike(pattern)))
            .order_by(Memory.updated_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def search_semantic_memories(
        self,
        user_id: int,
        query_vector: list[float],
        limit: int = 5,
        min_similarity: float = 0.35,
    ) -> list[tuple[Memory, float]]:
        """Find the top most semantically relevant memories using cosine similarity."""
        # Query all candidate memories for the user that have embeddings
        result = await self.db.execute(
            select(Memory).where(Memory.user_id == user_id, Memory.embedding.is_not(None))
        )
        memories = list(result.scalars().all())
        scored: list[tuple[Memory, float]] = []

        for mem in memories:
            if mem.embedding:
                score = cosine_similarity(query_vector, mem.embedding)
                if score >= min_similarity:
                    scored.append((mem, score))

        # Sort descending by similarity score
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:limit]

    async def store_memory(
        self,
        user_id: int,
        content: str,
        kind: MemoryKind = MemoryKind.LONG_TERM,
        tags: str | None = None,
        embedding: list[float] | None = None,
    ) -> Memory:
        memory = Memory(
            user_id=user_id,
            content=content.strip(),
            kind=kind,
            tags=tags,
            embedding=embedding,
        )
        self.db.add(memory)
        await self.db.commit()
        await self.db.refresh(memory)
        return memory

    async def update_memory(
        self,
        user_id: int,
        memory_id: int,
        content: str,
        tags: str | None = None,
        embedding: list[float] | None = None,
    ) -> Memory | None:
        memory = await self.get_memory(user_id, memory_id)
        if not memory:
            return None
        memory.content = content.strip()
        memory.tags = tags
        if embedding is not None:
            memory.embedding = embedding
        await self.db.commit()
        await self.db.refresh(memory)
        return memory

    async def get_memory(self, user_id: int, memory_id: int) -> Memory | None:
        result = await self.db.execute(select(Memory).where(Memory.user_id == user_id, Memory.id == memory_id))
        return result.scalar_one_or_none()

    async def delete_memory(self, user_id: int, memory_id: int) -> bool:
        result = await self.db.execute(delete(Memory).where(Memory.user_id == user_id, Memory.id == memory_id))
        await self.db.commit()
        return result.rowcount > 0
