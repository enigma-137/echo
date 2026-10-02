import json
import logging
from typing import Any, Optional

from app.memory.embeddings import EmbeddingProvider
from app.memory.manager import MemoryManager
from app.models.memory import MemoryKind
from app.providers.base import ModelProvider
from app.services.profile import ProfileService

logger = logging.getLogger(__name__)

EXTRACTION_SYSTEM_PROMPT = """
You are the Background Memory & Profile Extraction engine for Echo, a personal AI companion.
Analyze the following conversation turn between Emmanuel/User and Echo.

Determine if the user shared or updated any durable, long-term personal facts, preferences, relationships, hobbies, or lifestyle information.

CRITICAL GUIDELINES:
1. Only extract DURABLE long-term information (e.g., crushes, hobbies, dietary preferences, health goals, new projects, close friends, locations).
2. Do NOT extract ephemeral chatter (e.g., "what's the weather", "good morning", "thanks", "set a timer").
3. Format output strictly as JSON with this exact schema:
{
  "new_facts": [
    {
      "content": "Clear, concise 3rd-person factual statement (e.g. 'Emmanuel has a crush on Ileri and wants to go on a date with her.')",
      "tags": "comma-separated-tags"
    }
  ],
  "profile_updates": {
    "key_name": "value or nested dict/list to update in core profile"
  }
}
4. If no durable facts were mentioned, return:
{
  "new_facts": [],
  "profile_updates": {}
}

Return ONLY valid JSON. Do not include markdown codeblocks or preamble.
""".strip()


class MemoryExtractor:
    """Extracts durable facts and profile updates from conversation turns."""

    def __init__(
        self,
        provider: ModelProvider,
        memory_manager: MemoryManager,
        profile_service: ProfileService,
        embedding_provider: Optional[EmbeddingProvider] = None,
    ) -> None:
        self.provider = provider
        self.memory_manager = memory_manager
        self.profile_service = profile_service
        self.embedding_provider = embedding_provider

    async def process_turn(self, user_id: int, user_message: str, assistant_response: str) -> None:
        """Analyze the turn, extract facts, update profile, and store vectorized memories."""
        prompt = (
            f"{EXTRACTION_SYSTEM_PROMPT}\n\n"
            f"User message: {user_message}\n"
            f"Echo response: {assistant_response}\n\n"
            f"JSON Result:"
        )

        try:
            raw_result = await self.provider.complete_text(prompt)
            data = self._parse_json(raw_result)
            if not data:
                return

            new_facts = data.get("new_facts", [])
            profile_updates = data.get("profile_updates", {})

            # 1. Apply profile updates
            if profile_updates and isinstance(profile_updates, dict):
                logger.info("Auto-updating profile for user %s with %s", user_id, profile_updates)
                await self.profile_service.update_profile(user_id, profile_updates)

            # 2. Store & vectorize new facts
            for fact in new_facts:
                content = fact.get("content")
                if not content:
                    continue
                tags = fact.get("tags", "auto-extracted")
                
                embedding = None
                if self.embedding_provider:
                    try:
                        embedding = self.embedding_provider.embed_text(content)
                    except Exception as e:
                        logger.warning("Failed to generate embedding for fact: %s", e)

                stored = await self.memory_manager.store_memory(
                    user_id=user_id,
                    content=content,
                    kind=MemoryKind.LONG_TERM,
                    tags=tags,
                    embedding=embedding,
                )
                logger.info("Auto-extracted and stored memory ID %s: %s", stored.id, content)

        except Exception as e:
            logger.warning("Background memory extraction failed: %s", e)

    @staticmethod
    def _parse_json(text: str) -> Optional[dict[str, Any]]:
        text = text.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        try:
            return json.loads(text)
        except Exception:
            return None
