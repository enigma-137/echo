import logging
from typing import Optional

from app.memory.embeddings.base import EmbeddingProvider

logger = logging.getLogger(__name__)


class FastEmbedProvider(EmbeddingProvider):
    """Local, CPU-based embedding generation using fastembed (ONNX runtime)."""

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5") -> None:
        self.model_name = model_name
        self._model = None

    def _get_model(self):
        if self._model is None:
            try:
                from fastembed import TextEmbedding

                logger.info("Initializing FastEmbed model: %s", self.model_name)
                self._model = TextEmbedding(model_name=self.model_name)
            except Exception as e:
                logger.error("Failed to load FastEmbed model %s: %s", self.model_name, e)
                raise
        return self._model

    def embed_text(self, text: str) -> list[float]:
        model = self._get_model()
        # fastembed returns a generator of numpy arrays
        embeddings = list(model.embed([text]))
        return embeddings[0].tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        model = self._get_model()
        embeddings = list(model.embed(texts))
        return [e.tolist() for e in embeddings]
