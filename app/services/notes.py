from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.note import Note


class NotesService:
    def __init__(self, db: AsyncSession, user_id: int) -> None:
        self.db = db
        self.user_id = user_id

    async def create(self, title: str, content: str) -> Note:
        note = Note(user_id=self.user_id, title=title.strip(), content=content.strip())
        self.db.add(note)
        await self.db.commit()
        await self.db.refresh(note)
        return note

    async def list(self, query: str | None = None, limit: int = 20) -> list[Note]:
        stmt = select(Note).where(Note.user_id == self.user_id)
        if query:
            pattern = f"%{query}%"
            stmt = stmt.where(Note.title.ilike(pattern) | Note.content.ilike(pattern))
        result = await self.db.execute(stmt.order_by(Note.updated_at.desc()).limit(limit))
        return list(result.scalars().all())

    async def delete(self, note_id: int) -> bool:
        result = await self.db.execute(delete(Note).where(Note.user_id == self.user_id, Note.id == note_id))
        await self.db.commit()
        return result.rowcount > 0
