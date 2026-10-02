from app.services.notes import NotesService
from app.tools.base import EchoTool, ToolResult


class NotesTool(EchoTool):
    name = "notes"
    description = "Create, read, and delete notes."
    parameters = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["create", "list", "delete"]},
            "title": {"type": "string"},
            "content": {"type": "string"},
            "query": {"type": "string"},
            "note_id": {"type": "integer"},
        },
        "required": ["action"],
    }

    def __init__(self, service: NotesService) -> None:
        self.service = service

    async def run(self, arguments: dict) -> ToolResult:
        action = arguments.get("action")
        if action == "create":
            title = arguments.get("title") or "Untitled"
            content = arguments.get("content")
            if not content:
                return ToolResult(ok=False, error="content is required")
            note = await self.service.create(title, content)
            return ToolResult(data=self._serialize(note))
        if action == "list":
            notes = await self.service.list(arguments.get("query"))
            return ToolResult(data=[self._serialize(note) for note in notes])
        if action == "delete":
            note_id = arguments.get("note_id")
            if not note_id:
                return ToolResult(ok=False, error="note_id is required")
            return ToolResult(data={"deleted": await self.service.delete(int(note_id))})
        return ToolResult(ok=False, error=f"Unsupported notes action: {action}")

    @staticmethod
    def _serialize(note) -> dict:
        return {
            "id": note.id,
            "title": note.title,
            "content": note.content,
            "updated_at": note.updated_at.isoformat(),
        }
