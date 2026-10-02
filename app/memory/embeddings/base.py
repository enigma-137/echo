from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    """Abstract base class for generating text embeddings."""

    @abstractmethod
    def embed_text(self, text: str) -> list[float]:
        """Generate an embedding vector for a single string."""
        ...

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embedding vectors for a batch of strings."""
        ...
