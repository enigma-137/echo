from datetime import datetime

from app.services.reminders import ReminderService
from app.tools.base import EchoTool, ToolResult


class ReminderTool(EchoTool):
    name = "reminder"
    description = "Create, list, and delete reminders."
    parameters = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["create", "list", "delete"]},
            "title": {"type": "string"},
            "details": {"type": "string"},
            "remind_at": {"type": "string", "description": "ISO datetime when known"},
            "reminder_id": {"type": "integer"},
        },
        "required": ["action"],
    }

    def __init__(self, service: ReminderService) -> None:
        self.service = service

    async def run(self, arguments: dict) -> ToolResult:
        action = arguments.get("action")
        if action == "create":
            title = arguments.get("title")
            if not title:
                return ToolResult(ok=False, error="title is required")
            remind_at = self._parse_datetime(arguments.get("remind_at"))
            reminder = await self.service.create(title, remind_at, arguments.get("details"))
            return ToolResult(data=self._serialize(reminder))
        if action == "list":
            reminders = await self.service.list()
            return ToolResult(data=[self._serialize(reminder) for reminder in reminders])
        if action == "delete":
            reminder_id = arguments.get("reminder_id")
            if not reminder_id:
                return ToolResult(ok=False, error="reminder_id is required")
            return ToolResult(data={"deleted": await self.service.delete(int(reminder_id))})
        return ToolResult(ok=False, error=f"Unsupported reminder action: {action}")

    @staticmethod
    def _parse_datetime(value: str | None) -> datetime | None:
        if not value:
            return None
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    @staticmethod
    def _serialize(reminder) -> dict:
        return {
            "id": reminder.id,
            "title": reminder.title,
            "details": reminder.details,
            "remind_at": reminder.remind_at.isoformat() if reminder.remind_at else None,
            "completed": reminder.completed,
        }
