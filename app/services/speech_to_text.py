"""Speech-to-text providers for the Echo voice pipeline.

The provider is selected with ``STT_PROVIDER`` and can be swapped without
changing the `/voice` route. ``groq`` reuses the existing ``groq`` package
(Whisper) so no new dependency is introduced. ``mock`` returns a fixed
transcript so the whole pipeline is exercisable without keys.
"""

from __future__ import annotations

import io
import logging
from abc import ABC, abstractmethod

from app.config import Settings

logger = logging.getLogger(__name__)


class SpeechToTextProvider(ABC):
    """Provider-neutral contract for converting speech audio to text."""

    @abstractmethod
    async def transcribe(self, audio_bytes: bytes, filename: str, content_type: str) -> str:
        """Return the recognized transcript for ``audio_bytes``."""


class MockSTTProvider(SpeechToTextProvider):
    """Deterministic no-op STT for local smoke tests and CI."""

    async def transcribe(self, audio_bytes: bytes, filename: str, content_type: str) -> str:
        logger.info("MockSTTProvider returning fixed transcript (audio_size=%d)", len(audio_bytes))
        return "what can you do"


class GroqSTTProvider(SpeechToTextProvider):
    """Groq Whisper (Large v3) transcription endpoint."""

    def __init__(self, settings: Settings) -> None:
        if not settings.effective_stt_api_key:
            raise RuntimeError("STT_API_KEY or GROQ_API_KEY is required when STT_PROVIDER=groq")
        from groq import AsyncGroq

        self.model = settings.stt_model or "whisper-large-v3"
        self.client = AsyncGroq(api_key=settings.effective_stt_api_key)

    async def transcribe(self, audio_bytes: bytes, filename: str, content_type: str) -> str:
        logger.info("GroqSTTProvider transcribing audio_size=%d", len(audio_bytes))
        transcription = await self.client.audio.transcriptions.create(
            file=(filename, io.BytesIO(audio_bytes)),
            model=self.model,
        )
        text = (transcription.text or "").strip()
        logger.info("GroqSTTProvider transcription length=%d", len(text))
        return text


class SpitchSTTProvider(SpeechToTextProvider):
    """Spitch transcription, tuned for African languages and accents."""

    def __init__(self, settings: Settings) -> None:
        if not settings.spitch_api_key:
            raise RuntimeError("SPITCH_API_KEY is required when STT_PROVIDER=spitch")
        self.api_key = settings.spitch_api_key
        self.language = settings.spitch_stt_language
        self.timeout = settings.stt_request_timeout_seconds
        self.max_retries = settings.spitch_max_retries

    async def transcribe(self, audio_bytes: bytes, filename: str, content_type: str) -> str:
        from spitch import AsyncSpitch

        logger.info("SpitchSTTProvider transcribing audio_size=%d", len(audio_bytes))
        async with AsyncSpitch(
            api_key=self.api_key,
            timeout=self.timeout,
            max_retries=self.max_retries,
        ) as client:
            transcription = await client.speech.transcribe(
                content=(filename, audio_bytes, content_type),
                language=self.language,
            )
        text = (transcription.text or "").strip()
        logger.info("SpitchSTTProvider transcription length=%d", len(text))
        return text


def get_stt_provider(settings: Settings) -> SpeechToTextProvider:
    provider = (settings.stt_provider or "").lower()
    if provider in ("mock", "none", ""):
        return MockSTTProvider()
    if provider == "groq":
        from groq import AsyncGroq  # noqa: F401  (validate the package is importable)

        return GroqSTTProvider(settings)
    if provider == "spitch":
        return SpitchSTTProvider(settings)
    raise ValueError(f"Unsupported STT_PROVIDER: {settings.stt_provider}")


def stt_configured(settings: Settings) -> bool:
    provider = (settings.stt_provider or "").lower()
    if provider in ("mock", "none", ""):
        return True
    if provider == "groq":
        return bool(settings.effective_stt_api_key)
    if provider == "spitch":
        return bool(settings.spitch_api_key)
    return False
