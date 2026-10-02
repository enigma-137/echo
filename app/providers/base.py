from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field, field_validator


class ProviderMessage(BaseModel):
    role: str
    content: str


class ToolCallPlan(BaseModel):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class AgentPlan(BaseModel):
    response: str | None = None
    tool_calls: list[ToolCallPlan] = Field(default_factory=list)

    @field_validator("tool_calls", mode="before")
    @classmethod
    def normalize_tool_calls(cls, value: Any) -> Any:
        if value is None:
            return []
        return value


class ModelProvider(ABC):
    """Provider-neutral contract used by Echo's agent."""

    @abstractmethod
    async def complete_text(self, prompt: str) -> str:
        """Return plain text for a single prompt."""

    @abstractmethod
    async def plan(self, messages: list[ProviderMessage], tool_schemas: list[dict[str, Any]]) -> AgentPlan:
        """Return a natural-language response and optional tool calls."""

    @abstractmethod
    async def respond_with_tool_results(
        self,
        messages: list[ProviderMessage],
        tool_results: list[dict[str, Any]],
    ) -> str:
        """Create the user-facing response after Python executes tools."""
