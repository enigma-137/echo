import copy
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.memory.profile import USER_PROFILE
from app.models.user import User
from app.models.user_profile import UserProfile

logger = logging.getLogger(__name__)


DEFAULT_BASE_PROFILE: dict[str, Any] = {
    "name": "User",
    "preferred_name": "Friend",
    "occupation": [],
    "interests": [],
    "diet": {},
    "lifestyle": [],
    "goals": [],
}


class ProfileService:
    """Manages dynamic user profiles stored in the database."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_or_create_profile(self, user: User) -> dict[str, Any]:
        """Fetch the user's profile from the database, initializing with default data if needed."""
        result = await self.db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
        user_profile_record = result.scalar_one_or_none()

        if user_profile_record is not None:
            return user_profile_record.data

        initial_data = copy.deepcopy(USER_PROFILE)
        if user.preferred_name and "preferred_name" in initial_data:
            initial_data["preferred_name"] = user.preferred_name

        new_record = UserProfile(user_id=user.id, data=initial_data)
        self.db.add(new_record)
        await self.db.commit()
        await self.db.refresh(new_record)
        logger.info("Initialized dynamic UserProfile record for user %s", user.id)
        return new_record.data

    async def update_profile(self, user_id: int, updates: dict[str, Any]) -> dict[str, Any]:
        """Deeply update or patch specific fields in the user's profile."""
        result = await self.db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
        record = result.scalar_one_or_none()
        if record is None:
            record = UserProfile(user_id=user_id, data=DEFAULT_BASE_PROFILE)
            self.db.add(record)

        current_data = dict(record.data)
        for key, value in updates.items():
            if isinstance(value, dict) and isinstance(current_data.get(key), dict):
                current_data[key].update(value)
            elif isinstance(value, list) and isinstance(current_data.get(key), list):
                # Merge unique items into list
                for item in value:
                    if item not in current_data[key]:
                        current_data[key].append(item)
            else:
                current_data[key] = value

        record.data = current_data
        await self.db.commit()
        await self.db.refresh(record)
        return record.data
