import asyncio
import json
import logging
import re
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.prompts import get_system_prompt
from app.config import Settings
from app.memory.embeddings import EmbeddingProvider, FastEmbedProvider
from app.memory.extractor import MemoryExtractor
from app.memory.manager import MemoryManager
from app.memory.retriever import MemoryRetriever
from app.memory.summarizer import ConversationSummarizer
from app.providers.base import ModelProvider, ProviderMessage
from app.services.conversations import ConversationService
from app.services.profile import ProfileService
from app.tools.builder import build_tool_registry

logger = logging.getLogger(__name__)

# Shared instance to avoid reloading models on every request
_GLOBAL_EMBEDDING_PROVIDER: Optional[EmbeddingProvider] = None


def get_embedding_provider() -> Optional[EmbeddingProvider]:
    global _GLOBAL_EMBEDDING_PROVIDER
    if _GLOBAL_EMBEDDING_PROVIDER is None:
        try:
            _GLOBAL_EMBEDDING_PROVIDER = FastEmbedProvider()
        except Exception as e:
            logger.warning("Could not initialize FastEmbed provider: %s", e)
            _GLOBAL_EMBEDDING_PROVIDER = None
    return _GLOBAL_EMBEDDING_PROVIDER


class EchoAgent:
    """Coordinates dynamic profile, vector memory, model planning, tool execution, and auto-learning."""

    def __init__(self, db: AsyncSession, provider: ModelProvider, settings: Settings) -> None:
        self.db = db
        self.provider = provider
        self.settings = settings
        self.memory_manager = MemoryManager(db)
        self.profile_service = ProfileService(db)
        self.embedding_provider = get_embedding_provider()
        self.memory_retriever = MemoryRetriever(self.memory_manager, self.embedding_provider)
        self.memory_extractor = MemoryExtractor(
            self.provider,
            self.memory_manager,
            self.profile_service,
            self.embedding_provider,
        )

    async def chat(self, message: str) -> str:
        user = await self.memory_manager.get_or_create_default_user()
        user_profile = await self.profile_service.get_or_create_profile(user)
        user_name = user.preferred_name or user.name

        # 1. Dynamic prompt assembly
        system_prompt = get_system_prompt(user_profile, user_name)
        context = await self.memory_retriever.retrieve_context(
            user_id=user.id,
            query=message,
            timezone=self.settings.default_timezone,
            preferred_name=user_name,
        )

        registry = build_tool_registry(self.db, user.id, self.settings)

        messages = [
            ProviderMessage(role="system", content=system_prompt),
            ProviderMessage(role="context", content=context),
            ProviderMessage(role="user", content=message),
        ]

        try:
            plan = await asyncio.wait_for(
                self.provider.plan(messages, registry.schemas()),
                timeout=self.settings.model_request_timeout_seconds,
            )
        except TimeoutError:
            logger.exception(
                "Model plan() timed out after %s seconds (message=%r)",
                self.settings.model_request_timeout_seconds,
                message,
            )
            return (
                "I reached the Echo API, but the model provider did not respond before the timeout."
            )
        except Exception:
            logger.exception("Model plan() raised an unexpected exception (message=%r)", message)
            return (
                "I reached the Echo API, but the model call failed with an unexpected error. "
                "Check server logs for details."
            )

        if plan.tool_calls:
            tool_results = []
            for tool_call in plan.tool_calls:
                logger.info("Running tool %s with args %s", tool_call.name, tool_call.arguments)
                try:
                    result = await registry.run(tool_call.name, tool_call.arguments)
                except Exception:
                    logger.exception("Tool %s raised an exception", tool_call.name)
                    raise
                if not result.ok:
                    logger.warning("Tool %s returned an error: %s", tool_call.name, result.error)
                tool_results.append(
                    {
                        "tool": tool_call.name,
                        "arguments": tool_call.arguments,
                        "ok": result.ok,
                        "data": result.data,
                        "error": result.error,
                    }
                )
            try:
                response = await asyncio.wait_for(
                    self.provider.respond_with_tool_results(messages, tool_results),
                    timeout=self.settings.model_request_timeout_seconds,
                )
            except TimeoutError:
                logger.exception(
                    "Model respond_with_tool_results() timed out after %s seconds (message=%r, tool_results=%r)",
                    self.settings.model_request_timeout_seconds,
                    message,
                    tool_results,
                )
                response = "I ran the needed tool calls, but timed out while composing the final answer."
            except Exception:
                logger.exception(
                    "Model respond_with_tool_results() raised an unexpected exception",
                )
                response = "I ran the needed tools, but encountered an error while writing the final answer."
        else:
            response = plan.response or await self.provider.complete_text(message)

        response = self._normalize_response(response)

        # 2. Asynchronous Post-Turn Processing (Summary & Automated Fact Extraction)
        asyncio.create_task(self._post_chat_processing(user.id, message, response))

        return response

    async def _post_chat_processing(self, user_id: int, message: str, response: str) -> None:
        """Run summary saving and memory/profile extraction concurrently."""
        try:
            await asyncio.gather(
                self._save_conversation_summary(user_id, message, response),
                self.memory_extractor.process_turn(user_id, message, response),
                return_exceptions=True,
            )
        except Exception as e:
            logger.warning("Post-chat processing encountered an issue: %s", e)

    async def _save_conversation_summary(self, user_id: int, message: str, response: str) -> None:
        summarizer = ConversationSummarizer(self.provider)
        try:
            summary = await asyncio.wait_for(
                summarizer.summarize(message, response),
                timeout=self.settings.model_request_timeout_seconds,
            )
        except Exception:
            return
        if not summary:
            return
        lowered_summary = summary.lower()
        if "could not reach" in lowered_summary or "connection to google" in lowered_summary:
            return
        await ConversationService(self.db, user_id).save_summary(summary)

    @staticmethod
    def _normalize_response(response: str) -> str:
        stripped = response.strip()
        if not stripped.startswith("{"):
            return EchoAgent._strip_internal_chatter(response)
        try:
            payload = json.loads(stripped)
        except ValueError:
            return EchoAgent._strip_internal_chatter(response)
        if isinstance(payload, dict) and isinstance(payload.get("response"), str):
            return EchoAgent._strip_internal_chatter(payload["response"])
        return EchoAgent._strip_internal_chatter(response)

    @staticmethod
    def _strip_internal_chatter(response: str) -> str:
        banned_prefixes = (
            "i'll check",
            "i will check",
            "let me check",
            "let me search",
            "i searched",
            "i've searched",
            "i need to access",
            "to decide",
            "considering your profile",
            "considering your preferences",
            "considering your dietary preferences",
            "considering your diet",
        )
        lines = [line.strip() for line in response.strip().splitlines() if line.strip()]
        while lines and lines[0].lower().startswith(banned_prefixes):
            if "," in lines[0]:
                lines[0] = lines[0].split(",", maxsplit=1)[1].strip()
                break
            lines.pop(0)
        cleaned = "\n".join(lines).strip()
        cleaned = cleaned or response.strip()
        cleaned = re.sub(
            r"(?i)^considering your (profile|preferences|dietary preferences|diet),?\s*",
            "",
            cleaned,
        ).strip()
        if cleaned:
            cleaned = cleaned[0].upper() + cleaned[1:]
        return cleaned
