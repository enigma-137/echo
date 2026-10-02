from app.tools.base import EchoTool, ToolResult
from app.services.calendar import CalendarProvider


class CalendarTool(EchoTool):
    name = "calendar"
    description = "Read, search, create, update, and delete calendar events."
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["today", "read", "upcoming", "search", "create", "update", "delete"],
            },
            "event_id": {"type": "string"},
            "title": {"type": "string"},
            "starts_at": {"type": "string"},
            "ends_at": {"type": "string"},
            "description": {"type": "string"},
            "location": {"type": "string"},
            "timezone": {"type": "string"},
            "query": {"type": "string"},
            "days": {"type": "integer"},
            "limit": {"type": "integer"},
        },
        "required": ["action"],
    }

    def __init__(self, provider: CalendarProvider) -> None:
        self.provider = provider

    async def run(self, arguments: dict) -> ToolResult:
        action = arguments.get("action")
        if action in {"today", "read"}:
            return await self._result(self.provider.today())
        if action == "upcoming":
            return await self._result(
                self.provider.upcoming(days=int(arguments.get("days") or 7), limit=int(arguments.get("limit") or 20))
            )
        if action == "search":
            query = arguments.get("query")
            if not query:
                return ToolResult(ok=False, error="query is required")
            return await self._result(
                self.provider.search(query, days=int(arguments.get("days") or 30), limit=int(arguments.get("limit") or 10))
            )
        if action == "create":
            return await self._result(self.provider.create_event(arguments))
        if action == "update":
            event_id = arguments.get("event_id")
            if not event_id:
                return ToolResult(ok=False, error="event_id is required")
            return await self._result(self.provider.update_event(event_id, arguments))
        if action == "delete":
            event_id = arguments.get("event_id")
            if not event_id:
                return ToolResult(ok=False, error="event_id is required")
            return await self._result(self.provider.delete_event(event_id))
        return ToolResult(ok=False, error=f"Unsupported calendar action: {action}")

    @staticmethod
    async def _result(awaitable) -> ToolResult:
        data = await awaitable
        if data.get("ok") is False:
            return ToolResult(ok=False, data=data, error=data.get("error"))
        return ToolResult(data=data)
