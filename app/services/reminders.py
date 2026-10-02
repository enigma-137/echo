from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reminder import Reminder


class ReminderService:
    def __init__(self, db: AsyncSession, user_id: int) -> None:
        self.db = db
        self.user_id = user_id

    async def create(self, title: str, remind_at: datetime | None = None, details: str | None = None) -> Reminder:
        reminder = Reminder(user_id=self.user_id, title=title.strip(), remind_at=remind_at, details=details)
        self.db.add(reminder)
        await self.db.commit()
        await self.db.refresh(reminder)
        return reminder

    async def list(self, include_completed: bool = False, limit: int = 20) -> list[Reminder]:
        stmt = select(Reminder).where(Reminder.user_id == self.user_id)
        if not include_completed:
            stmt = stmt.where(Reminder.completed.is_(False))
        result = await self.db.execute(stmt.order_by(Reminder.remind_at.asc().nullslast()).limit(limit))
        return list(result.scalars().all())

    async def delete(self, reminder_id: int) -> bool:
        result = await self.db.execute(delete(Reminder).where(Reminder.user_id == self.user_id, Reminder.id == reminder_id))
        await self.db.commit()
        return result.rowcount > 0
