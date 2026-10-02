from app.tools.base import EchoTool, ToolResult


class ToolRegistry:
    def __init__(self, tools: list[EchoTool]) -> None:
        self._tools = {tool.name: tool for tool in tools}

    def schemas(self) -> list[dict]:
        return [tool.schema() for tool in self._tools.values()]

    async def run(self, name: str, arguments: dict) -> ToolResult:
        tool = self._tools.get(name)
        if not tool:
            return ToolResult(ok=False, error=f"Unknown tool: {name}")
        return await tool.run(arguments)
