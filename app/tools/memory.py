from app.memory.manager import MemoryManager
from app.models.memory import MemoryKind
from app.tools.base import EchoTool, ToolResult


class MemoryTool(EchoTool):
    name = "memory"
    description = "Search, store, update, or delete Echo's long-term memories."
    parameters = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["search", "store", "update", "delete"]},
            "query": {"type": "string"},
            "content": {"type": "string"},
            "memory_id": {"type": "integer"},
            "tags": {"type": "string"},
        },
        "required": ["action"],
    }

    def __init__(self, manager: MemoryManager, user_id: int) -> None:
        self.manager = manager
        self.user_id = user_id

    async def run(self, arguments: dict) -> ToolResult:
        action = arguments.get("action")
        if action == "search":
            query = arguments.get("query", "")
            memories = await self.manager.search_memories(self.user_id, query)
            return ToolResult(data=[self._serialize(memory) for memory in memories])
        if action == "store":
            content = arguments.get("content")
            if not content:
                return ToolResult(ok=False, error="content is required")
            memory = await self.manager.store_memory(
                self.user_id,
                content,
                kind=MemoryKind.LONG_TERM,
                tags=arguments.get("tags"),
            )
            return ToolResult(data=self._serialize(memory))
        if action == "update":
            memory_id = arguments.get("memory_id")
            content = arguments.get("content")
            if not memory_id or not content:
                return ToolResult(ok=False, error="memory_id and content are required")
            memory = await self.manager.update_memory(self.user_id, int(memory_id), content, arguments.get("tags"))
            return ToolResult(data=self._serialize(memory) if memory else None, ok=memory is not None)
        if action == "delete":
            memory_id = arguments.get("memory_id")
            if not memory_id:
                return ToolResult(ok=False, error="memory_id is required")
            return ToolResult(data={"deleted": await self.manager.delete_memory(self.user_id, int(memory_id))})
        return ToolResult(ok=False, error=f"Unsupported memory action: {action}")

    @staticmethod
    def _serialize(memory) -> dict:
        return {
            "id": memory.id,
            "kind": memory.kind.value,
            "content": memory.content,
            "tags": memory.tags,
            "updated_at": memory.updated_at.isoformat(),
        }
