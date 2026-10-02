from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


class ToolResult(BaseModel):
    ok: bool = True
    data: Any = None
    error: str | None = None


class EchoTool(ABC):
    name: str
    description: str
    parameters: dict[str, Any] = {}

    @abstractmethod
    async def run(self, arguments: dict[str, Any]) -> ToolResult:
        """Execute a tool with validated arguments."""

    def schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }
