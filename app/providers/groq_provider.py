import json
from typing import Any

from groq import APIError, AsyncGroq

from app.config import Settings
from app.providers.base import AgentPlan, ModelProvider, ProviderMessage


class GroqProvider(ModelProvider):
    """Groq-hosted open-weight model (e.g. Llama 3.3 70B) implementation of
    Echo's model-provider interface. Groq exposes an OpenAI-compatible chat
    completions API, so this mirrors GeminiProvider's "build one prompt, ask
    for JSON back" pattern almost exactly.
    """

    def __init__(self, settings: Settings) -> None:
        if not settings.groq_api_key:
            raise RuntimeError("GROQ_API_KEY is required when MODEL_PROVIDER=groq")
        self.model = settings.groq_model or "llama-3.3-70b-versatile"
        self.client = AsyncGroq(api_key=settings.groq_api_key)

    async def complete_text(self, prompt: str) -> str:
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.choices[0].message.content or ""
        except Exception as exc:
            return self._friendly_error(exc)

    async def plan(self, messages: list[ProviderMessage], tool_schemas: list[dict[str, Any]]) -> AgentPlan:
        prompt = self._messages_to_prompt(messages)
        prompt += (
            "\n\nAvailable Python tools:\n"
            f"{json.dumps(tool_schemas, indent=2)}\n\n"
            "Planning rules:\n"
            "- Decide whether tools are required before answering.\n"
            "- Never narrate internal steps to the user. Do not say you will check, search, access profile, use memory, or call a tool.\n"
            "- Do not say 'considering your profile/preferences/diet'; just answer like you already know him.\n"
            "- If no tool is needed, answer naturally and casually as Echo, Emmanuel's close friend.\n"
            "- For facts already present in the SYSTEM user profile, answer directly. There is no profile tool.\n"
            "- For profile facts such as height, diet, favorite foods, disliked foods, goals, work, friends, nickname, or lifestyle, do not call memory.\n"
            "- If the user asks about weather, forecasts, rain, temperature, humidity, wind, or UV, call weather.\n"
            "- If the user asks about calendar events, meetings, schedules, or event changes, call calendar.\n"
            "- If a calendar result includes time_until, use it exactly for countdowns instead of recalculating.\n- If the user asks about Gmail, inbox, email search, messages, threads, or drafts, call email.\n- Never send email unless the user clearly confirms the exact send action. Prefer create_draft when unsure.\n"
            "- If the user asks you to remember, update, search, or forget durable information, call memory.\n"
            "- If the user asks about reminders, call reminder.\n"
            "- Use multiple tool_calls when one request needs multiple tools.\n"
            "- If required tool arguments are missing, answer with a concise follow-up question and no tool_calls.\n\n"
            "Examples:\n"
            'User: "What is the weather tomorrow?" -> {"response": null, "tool_calls": [{"name": "weather", "arguments": {"action": "forecast", "location": "Ogun State", "days": 2}}]}\n'
            'User: "What is on my calendar today?" -> {"response": null, "tool_calls": [{"name": "calendar", "arguments": {"action": "today"}}]}\nUser: "Find my latest email from Ronit." -> {"response": null, "tool_calls": [{"name": "email", "arguments": {"action": "search", "query": "from:Ronit", "limit": 5}}]}\n'
            'User: "Remember that I prefer coffee." -> {"response": null, "tool_calls": [{"name": "memory", "arguments": {"action": "store", "content": "Emmanuel prefers coffee.", "tags": "preference"}}]}\n'
            'User: "Will it rain tomorrow and what meetings do I have?" -> {"response": null, "tool_calls": [{"name": "weather", "arguments": {"action": "forecast", "location": "Ogun State", "days": 2}}, {"name": "calendar", "arguments": {"action": "upcoming", "days": 1}}]}\n\n'
            "Return only valid JSON matching this schema: "
            '{"response": "short answer if no tools are needed", '
            '"tool_calls": [{"name": "tool_name", "arguments": {"key": "value"}}]}. '
            "If a tool is useful, include tool_calls and leave response null."
        )
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
            )
        except Exception as exc:
            return AgentPlan(response=self._friendly_error(exc), tool_calls=[])
        raw = response.choices[0].message.content or "{}"
        try:
            return AgentPlan.model_validate_json(raw)
        except ValueError:
            return AgentPlan(response=raw, tool_calls=[])

    async def respond_with_tool_results(
        self,
        messages: list[ProviderMessage],
        tool_results: list[dict[str, Any]],
    ) -> str:
        prompt = self._messages_to_prompt(messages)
        prompt += (
            "\n\nPython executed these tool results:\n"
            f"{json.dumps(tool_results, indent=2, default=str)}\n\n"
            "Reply to the user concisely. Do not claim a tool succeeded if its result says it failed. "
            "For calendar countdowns, use the `time_until.human` and `time_until.status` fields from Python. "
            "Do not mention Python, tools, tool results, profile access, or memory access. "
            "Do not say 'considering your profile/preferences/diet'; just speak naturally. "
            "Sound like Emmanuel's close friend: casual, warm, direct, and useful."
        )
        return await self.complete_text(prompt)

    @staticmethod
    def _messages_to_prompt(messages: list[ProviderMessage]) -> str:
        return "\n\n".join(f"{message.role.upper()}:\n{message.content}" for message in messages)

    @staticmethod
    def _friendly_error(error: Exception) -> str:
        if isinstance(error, APIError):
            return f"Groq API returned an error: {error}"
        message = str(error) or error.__class__.__name__
        if "api.groq.com" in message or "ConnectionResetError" in message:
            return (
                "I could not reach Groq right now. The connection to Groq's API was reset, "
                "which is usually network, DNS, firewall, VPN, or SSL-related rather than a bad API key."
            )
        return f"I could not reach the model provider right now: {message}"
