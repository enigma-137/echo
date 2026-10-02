from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation


class ConversationService:
    def __init__(self, db: AsyncSession, user_id: int) -> None:
        self.db = db
        self.user_id = user_id

    async def save_summary(self, summary: str) -> Conversation:
        conversation = Conversation(user_id=self.user_id, summary=summary.strip())
        self.db.add(conversation)
        await self.db.commit()
        await self.db.refresh(conversation)
        return conversation
