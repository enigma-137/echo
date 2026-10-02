"""Text-to-speech providers for the Echo voice pipeline.

Selected with ``TTS_PROVIDER``. ``mock`` (default) synthesizes a short sine
tone into a standards-compliant 16-bit PCM WAV using only the stdlib, so the
pipeline runs end-to-end without any paid account. ``openai`` is an optional
provider that lazily imports ``openai`` only when selected.
"""

from __future__ import annotations

import logging
import math
from abc import ABC, abstractmethod

import httpx

from app.config import Settings
from app.services.audio import encode_wav, normalize_to_format

logger = logging.getLogger(__name__)


class TextToSpeechProvider(ABC):
    """Provider-neutral contract for converting text to speech audio bytes."""

    @abstractmethod
    async def synthesize(self, text: str) -> bytes:
        """Return WAV (16-bit PCM) bytes at the configured sample rate/channels."""


class MockTTSProvider(TextToSpeechProvider):
    """Generates a deterministic tone proportional to text length. Used for tests/CI."""

    def __init__(self, settings: Settings) -> None:
        self.sample_rate = settings.audio_sample_rate
        self.channels = settings.audio_channels

    async def synthesize(self, text: str) -> bytes:
        duration = max(0.2, min(0.04 * max(len(text), 1), 4.0))
        n_samples = int(self.sample_rate * duration)
        samples = [
            int(0.6 * 32767 * math.sin(2 * math.pi * 440 * i / self.sample_rate))
            for i in range(n_samples)
        ]
        audio = encode_wav(samples, self.sample_rate, self.channels)
        logger.info("MockTTSProvider synthesized audio_size=%d text_length=%d", len(audio), len(text))
        return audio


class OpenAITTSProvider(TextToSpeechProvider):
    """OpenAI TTS over HTTP, using the project's existing httpx dependency."""

    def __init__(self, settings: Settings) -> None:
        if not settings.tts_api_key:
            raise RuntimeError("TTS_API_KEY is required when TTS_PROVIDER=openai")
        self.api_key = settings.tts_api_key
        self.model = settings.tts_model or "tts-1"
        self.voice = settings.tts_voice or "nova"
        self.sample_rate = settings.audio_sample_rate
        self.channels = settings.audio_channels
        self.timeout = settings.tts_request_timeout_seconds

    async def synthesize(self, text: str) -> bytes:
        logger.info("OpenAITTSProvider synthesizing text_length=%d", len(text))
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                "https://api.openai.com/v1/audio/speech",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "voice": self.voice,
                    "input": text,
                    "response_format": "wav",
                },
            )
            response.raise_for_status()
            raw_wav = response.content
        if self.sample_rate != 24000 or self.channels != 1:
            raw_wav = normalize_to_format(raw_wav, self.sample_rate, self.channels)
        logger.info("OpenAITTSProvider audio_size=%d", len(raw_wav))
        return raw_wav


class SpitchTTSProvider(TextToSpeechProvider):
    """Spitch speech generation returning ESP32-ready normalized WAV audio."""

    def __init__(self, settings: Settings) -> None:
        if not settings.spitch_api_key:
            raise RuntimeError("SPITCH_API_KEY is required when TTS_PROVIDER=spitch")
        self.api_key = settings.spitch_api_key
        self.language = settings.spitch_tts_language
        self.voice = settings.spitch_tts_voice
        self.speed = settings.spitch_tts_speed
        self.sample_rate = settings.audio_sample_rate
        self.channels = settings.audio_channels
        self.timeout = settings.tts_request_timeout_seconds
        self.max_retries = settings.spitch_max_retries

    async def synthesize(self, text: str) -> bytes:
        from spitch import AsyncSpitch

        logger.info("SpitchTTSProvider synthesizing text_length=%d", len(text))
        async with AsyncSpitch(
            api_key=self.api_key,
            timeout=self.timeout,
            max_retries=self.max_retries,
        ) as client:
            response = await client.speech.generate(
                text=text,
                voice=self.voice,
                language=self.language,
                speed=self.speed,
                format="wav",
            )
            raw_wav = await response.read()
        audio = normalize_to_format(raw_wav, self.sample_rate, self.channels)
        logger.info("SpitchTTSProvider audio_size=%d", len(audio))
        return audio


def get_tts_provider(settings: Settings) -> TextToSpeechProvider:
    provider = (settings.tts_provider or "").lower()
    if provider in ("mock", "none", ""):
        return MockTTSProvider(settings)
    if provider == "openai":
        return OpenAITTSProvider(settings)
    if provider == "spitch":
        return SpitchTTSProvider(settings)
    raise ValueError(f"Unsupported TTS_PROVIDER: {settings.tts_provider}")


def tts_configured(settings: Settings) -> bool:
    provider = (settings.tts_provider or "").lower()
    if provider in ("mock", "none", ""):
        return True
    if provider == "openai":
        return bool(settings.tts_api_key)
    if provider == "spitch":
        return bool(settings.spitch_api_key)
    return False
