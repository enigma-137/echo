import json
from typing import Any

from google.genai.errors import APIError
from google import genai
from google.genai import types

from app.config import Settings
from app.providers.base import AgentPlan, ModelProvider, ProviderMessage


class GeminiProvider(ModelProvider):
    """Google Gemini implementation of Echo's model-provider interface."""

    def __init__(self, settings: Settings) -> None:
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is required when MODEL_PROVIDER=gemini")
        self.model = settings.gemini_model
        self.client = genai.Client(api_key=settings.gemini_api_key)

    async def complete_text(self, prompt: str) -> str:
        try:
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=prompt,
            )
            return response.text or ""
        except Exception as exc:
            return self._friendly_error(exc)

    async def plan(self, messages: list[ProviderMessage], tool_schemas: list[dict[str, Any]]) -> AgentPlan:
        prompt = self._messages_to_prompt(messages)
        prompt += (
            "\n\nAvailable Python tools:\n"
            f"{json.dumps(tool_schemas, indent=2)}\n\n"
            "Planning rules:\n"
            "- Decide whether tools are required before answering.\n"
            "- If the user asks about weather, forecasts, rain, temperature, humidity, wind, or UV, call weather.\n"
            "- If the user asks about calendar events, meetings, schedules, or event changes, call calendar.\n"
            "- If the user asks you to remember, update, search, or forget durable information, call memory.\n"
            "- If the user asks about reminders, call reminder.\n"
            "- Use multiple tool_calls when one request needs multiple tools.\n"
            "- If required tool arguments are missing, answer with a concise follow-up question and no tool_calls.\n\n"
            "Examples:\n"
            'User: "What is the weather tomorrow?" -> {"response": null, "tool_calls": [{"name": "weather", "arguments": {"action": "forecast", "location": "Ogun State", "days": 2}}]}\n'
            'User: "What is on my calendar today?" -> {"response": null, "tool_calls": [{"name": "calendar", "arguments": {"action": "today"}}]}\n'
            'User: "Remember that I prefer coffee." -> {"response": null, "tool_calls": [{"name": "memory", "arguments": {"action": "store", "content": "Emmanuel prefers coffee.", "tags": "preference"}}]}\n'
            'User: "Will it rain tomorrow and what meetings do I have?" -> {"response": null, "tool_calls": [{"name": "weather", "arguments": {"action": "forecast", "location": "Ogun State", "days": 2}}, {"name": "calendar", "arguments": {"action": "upcoming", "days": 1}}]}\n\n'
            "Return only valid JSON matching this schema: "
            '{"response": "short answer if no tools are needed", '
            '"tool_calls": [{"name": "tool_name", "arguments": {"key": "value"}}]}. '
            "If a tool is useful, include tool_calls and leave response null."
        )
        try:
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )
        except Exception as exc:
            return AgentPlan(response=self._friendly_error(exc), tool_calls=[])
        try:
            return AgentPlan.model_validate_json(response.text or "{}")
        except ValueError:
            return AgentPlan(response=response.text or "I could not create a valid plan.", tool_calls=[])

    async def respond_with_tool_results(
        self,
        messages: list[ProviderMessage],
        tool_results: list[dict[str, Any]],
    ) -> str:
        prompt = self._messages_to_prompt(messages)
        prompt += (
            "\n\nPython executed these tool results:\n"
            f"{json.dumps(tool_results, indent=2, default=str)}\n\n"
            "Reply to the user concisely. Do not claim a tool succeeded if its result says it failed."
        )
        return await self.complete_text(prompt)

    @staticmethod
    def _messages_to_prompt(messages: list[ProviderMessage]) -> str:
        return "\n\n".join(f"{message.role.upper()}:\n{message.content}" for message in messages)

    @staticmethod
    def _friendly_error(error: Exception) -> str:
        if isinstance(error, APIError):
            return f"Gemini API returned an error: {error}"
        message = str(error) or error.__class__.__name__
        if "generativelanguage.googleapis.com" in message or "ConnectionResetError" in message:
            return (
                "I could not reach Gemini right now. The connection to Google's Gemini API was reset, "
                "which is usually network, DNS, firewall, VPN, or SSL-related rather than a bad API key."
            )
        return f"I could not reach the model provider right now: {message}"
