from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.memory.manager import MemoryManager
from app.services.calendar import get_calendar_provider
from app.services.notes import NotesService
from app.services.reminders import ReminderService
from app.tools.calendar import CalendarTool
from app.tools.memory import MemoryTool
from app.tools.notes import NotesTool
from app.tools.registry import ToolRegistry
from app.tools.reminder import ReminderTool
from app.tools.weather import WeatherTool


def build_tool_registry(db: AsyncSession, user_id: int, settings: Settings) -> ToolRegistry:
    memory_manager = MemoryManager(db)
    return ToolRegistry(
        [
            WeatherTool(settings),
            CalendarTool(get_calendar_provider(settings)),
            MemoryTool(memory_manager, user_id),
            NotesTool(NotesService(db, user_id)),
            ReminderTool(ReminderService(db, user_id)),
        ]
    )
