from app.config import Settings, get_settings
from app.providers.base import ModelProvider
from app.providers.gemini import GeminiProvider
from app.providers.groq_provider import GroqProvider
from app.providers.mock import MockProvider


def get_model_provider(settings: Settings | None = None) -> ModelProvider:
    settings = settings or get_settings()
    provider = settings.model_provider.lower()
    if provider == "gemini":
        return GeminiProvider(settings)
    if provider == "groq":
        return GroqProvider(settings)
    if provider == "mock":
        return MockProvider()
    raise ValueError(f"Unsupported MODEL_PROVIDER: {settings.model_provider}")