from app.providers.base import AgentPlan, ModelProvider, ProviderMessage


class MockProvider(ModelProvider):
    """Local fallback for smoke tests when no external API key is present."""

    async def complete_text(self, prompt: str) -> str:
        return "No external model key is configured yet. Echo is running in mock mode."

    async def plan(self, messages: list[ProviderMessage], tool_schemas: list[dict]) -> AgentPlan:
        latest = messages[-1].content if messages else ""
        return AgentPlan(response=f"Echo mock mode received: {latest}", tool_calls=[])

    async def respond_with_tool_results(self, messages: list[ProviderMessage], tool_results: list[dict]) -> str:
        return f"Done. Tool results: {tool_results}"
