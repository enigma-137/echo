from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.schemas import HealthResponse
from app.services.speech_to_text import stt_configured
from app.services.text_to_speech import tts_configured

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        environment=settings.environment,
        voice={
            "configured": stt_configured(settings) and tts_configured(settings),
            "stt_provider": settings.stt_provider,
            "tts_provider": settings.tts_provider,
            "output": {
                "container": "wav",
                "encoding": "pcm_s16le",
                "sample_rate": settings.audio_sample_rate,
                "channels": settings.audio_channels,
            },
        },
    )
