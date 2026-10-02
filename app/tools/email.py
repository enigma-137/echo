from app.services.gmail import GmailService
from app.tools.base import EchoTool, ToolResult


class EmailTool(EchoTool):
    name = "email"
    description = "Search Gmail, read messages or threads, create drafts, and send email after explicit confirmation."
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["recent", "search", "read_message", "read_thread", "create_draft", "send_email"],
            },
            "query": {"type": "string"},
            "limit": {"type": "integer"},
            "message_id": {"type": "string"},
            "thread_id": {"type": "string"},
            "to": {"type": "string"},
            "subject": {"type": "string"},
            "body": {"type": "string"},
            "confirm_send": {"type": "boolean"},
        },
        "required": ["action"],
    }

    def __init__(self, service: GmailService) -> None:
        self.service = service

    async def run(self, arguments: dict) -> ToolResult:
        action = arguments.get("action")
        if action == "recent":
            return await self._result(self.service.recent(limit=int(arguments.get("limit") or 10)))
        if action == "search":
            query = arguments.get("query")
            if not query:
                return ToolResult(ok=False, error="query is required")
            return await self._result(self.service.search(query, limit=int(arguments.get("limit") or 10)))
        if action == "read_message":
            message_id = arguments.get("message_id")
            if not message_id:
                return ToolResult(ok=False, error="message_id is required")
            return await self._result(self.service.read_message(message_id))
        if action == "read_thread":
            thread_id = arguments.get("thread_id")
            if not thread_id:
                return ToolResult(ok=False, error="thread_id is required")
            return await self._result(self.service.read_thread(thread_id))
        if action == "create_draft":
            missing = [name for name in ("to", "subject", "body") if not arguments.get(name)]
            if missing:
                return ToolResult(ok=False, error=f"Missing draft fields: {', '.join(missing)}")
            return await self._result(
                self.service.create_draft(
                    to=arguments["to"],
                    subject=arguments["subject"],
                    body=arguments["body"],
                    thread_id=arguments.get("thread_id"),
                )
            )
        if action == "send_email":
            if arguments.get("confirm_send") is not True:
                return ToolResult(ok=False, error="send_email requires confirm_send=true after explicit user confirmation")
            missing = [name for name in ("to", "subject", "body") if not arguments.get(name)]
            if missing:
                return ToolResult(ok=False, error=f"Missing send fields: {', '.join(missing)}")
            return await self._result(
                self.service.send_email(
                    to=arguments["to"],
                    subject=arguments["subject"],
                    body=arguments["body"],
                    thread_id=arguments.get("thread_id"),
                )
            )
        return ToolResult(ok=False, error=f"Unsupported email action: {action}")

    @staticmethod
    async def _result(awaitable) -> ToolResult:
        data = await awaitable
        if data.get("ok") is False:
            return ToolResult(ok=False, data=data, error=data.get("error"))
        return ToolResult(data=data)
