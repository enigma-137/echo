from datetime import datetime
import logging
from typing import Optional
from zoneinfo import ZoneInfo

from app.memory.embeddings import EmbeddingProvider
from app.memory.manager import MemoryManager
from app.models.memory import MemoryKind

logger = logging.getLogger(__name__)


class MemoryRetriever:
    """Retrieves relevant long-term and semantic memories for incoming user queries."""

    def __init__(
        self,
        memory_manager: MemoryManager,
        embedding_provider: Optional[EmbeddingProvider] = None,
    ) -> None:
        self.memory_manager = memory_manager
        self.embedding_provider = embedding_provider

    async def retrieve_context(
        self,
        user_id: int,
        query: str,
        timezone: str = "Africa/Lagos",
        preferred_name: str = "Emmanuel",
    ) -> str:
        """Assemble the temporal and semantic memory context for the LLM prompt."""
        now = datetime.now(ZoneInfo(timezone))
        time_context = f"Current local time for {preferred_name}: {now.isoformat()} ({timezone})."

        semantic_memories = []
        if self.embedding_provider and query:
            try:
                query_vector = self.embedding_provider.embed_text(query)
                scored = await self.memory_manager.search_semantic_memories(
                    user_id=user_id,
                    query_vector=query_vector,
                    limit=6,
                    min_similarity=0.35,
                )
                semantic_memories = [m for m, score in scored if m.kind != MemoryKind.PROFILE]
            except Exception as e:
                logger.warning("Semantic vector retrieval failed, falling back to recent list: %s", e)

        # Fallback to recent long-term memories if vector search returns empty or wasn't available
        if not semantic_memories:
            all_recent = await self.memory_manager.list_memories(user_id, limit=6)
            semantic_memories = [m for m in all_recent if m.kind != MemoryKind.PROFILE]

        if not semantic_memories:
            return f"{time_context}\nNo stored long-term or conversation memories yet."

        formatted_memories = "\n".join(
            f"- [{m.kind.value}] {m.content}" for m in semantic_memories
        )
        return f"{time_context}\nRelevant stored memories & context:\n{formatted_memories}"
