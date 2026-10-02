import asyncio
import logging
import time
from typing import Any

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.database import get_db
from app.services.audio import HEADER_MAGIC, decode_wav
from app.services.echo_service import generate_echo_response
from app.services.speech_to_text import get_stt_provider
from app.services.text_to_speech import get_tts_provider

router = APIRouter(tags=["voice"])
logger = logging.getLogger("echo.voice")

SUPPORTED_CONTENT_TYPES = {"audio/wav", "audio/x-wav", "audio/wave"}
SUPPORTED_EXTENSIONS = {".wav"}
MAX_HEADER_TEXT_CHARS = 200


class _ValidationError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail


class _LimitExceeded(Exception):
    pass


class _StageTimeout(Exception):
    pass


def _header_text(value: str | None) -> str:
    """Make a string safe for an HTTP header: printable, ascii, length-bounded."""
    if not value:
        return ""
    cleaned = "".join(ch for ch in value if ch.isprintable())
    cleaned = cleaned.encode("ascii", errors="replace").decode("ascii")
    if len(cleaned) > MAX_HEADER_TEXT_CHARS:
        cleaned = cleaned[:MAX_HEADER_TEXT_CHARS] + "..."
    return cleaned


def _error(status_code: int, detail: str, **extra: Any) -> JSONResponse:
    body: dict[str, Any] = {"error": detail}
    body.update(extra)
    headers = {"X-Echo-Error": _header_text(detail)}
    return JSONResponse(status_code=status_code, content=body, headers=headers)


async def _read_with_limit(file: UploadFile, max_bytes: int) -> bytes:
    """Read ``file`` into memory, enforcing ``max_bytes``. Returns b"" if empty."""
    total = 0
    chunks: list[bytes] = []
    while True:
        chunk = await file.read(65536)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise _LimitExceeded()
        chunks.append(chunk)
    return b"".join(chunks)


async def _with_timeout(coro: Any, timeout: float) -> Any:
    """Wrap an awaitable with a timeout, converting asyncio.TimeoutError."""
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError as exc:
        raise _StageTimeout() from exc


async def _validate_audio_file(audio: UploadFile | None, settings: Settings) -> bytes:
    """Validate presence/format/size of the upload and return the WAV bytes."""
    if audio is None or audio.filename is None:
        raise _ValidationError(400, "No audio file provided. Send a WAV file as the 'audio' field.")

    content_type = (audio.content_type or "").lower()
    ext_ok = any(audio.filename.lower().endswith(ext) for ext in SUPPORTED_EXTENSIONS)
    if content_type not in SUPPORTED_CONTENT_TYPES and not ext_ok:
        raise _ValidationError(
            415,
            f"Unsupported audio format. Send a .wav file "
            f"(got filename={audio.filename!r}, content_type={content_type!r}).",
        )

    max_bytes = int(settings.max_voice_upload_mb * 1024 * 1024)
    try:
        audio_bytes = await _read_with_limit(audio, max_bytes)
    except _LimitExceeded:
        raise _ValidationError(413, f"Audio upload exceeds the {settings.max_voice_upload_mb} MB limit.")
    if not audio_bytes:
        raise _ValidationError(400, "The uploaded audio file is empty.")

    if audio_bytes[: len(HEADER_MAGIC)] != HEADER_MAGIC:
        raise _ValidationError(415, "Uploaded file is not a WAV file (missing RIFF header).")

    try:
        params = decode_wav(audio_bytes)
    except ValueError as exc:
        raise _ValidationError(415, f"Corrupt or unsupported recording: {exc}")

    logger.info(
        "voice request: file=%s content_type=%s size=%d sr=%d channels=%d",
        audio.filename,
        content_type,
        len(audio_bytes),
        params["sample_rate"],
        params["channels"],
    )
    return audio_bytes


@router.post("/voice")
async def voice(
    audio: UploadFile | None = File(default=None),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Any:
    """Transcribe microphone audio (WAV), run it through Echo, and return spoken audio.

    ESP32 contract:
        POST /voice  (multipart/form-data)
            field name: audio  (a .wav file, 16-bit PCM, mono 16 kHz recommended)
        Response on success:
            200  Content-Type: audio/wav
            headers: X-Echo-Transcript, X-Echo-Response
            body:   WAV bytes playable by the Bluetooth A2DP sink
    Errors are returned as JSON with an X-Echo-Error header.
    """
    pipeline_start = time.perf_counter()
    logger.info("voice request received")

    try:
        audio_bytes = await _validate_audio_file(audio, settings)
    except _ValidationError as exc:
        logger.warning("voice validation failed: %s", exc.detail)
        return _error(exc.status_code, exc.detail)
    finally:
        if audio is not None:
            try:
                await audio.close()
            except Exception:  # noqa: BLE001
                pass

    filename = audio.filename if audio and audio.filename else "audio.wav"
    content_type = audio.content_type if audio and audio.content_type else "audio/wav"

    transcript = ""
    response_text = ""
    try:
        stt_provider = get_stt_provider(settings)
        stage = time.perf_counter()
        logger.info("transcription started (provider=%s)", settings.stt_provider)
        transcript = await _with_timeout(
            stt_provider.transcribe(audio_bytes, filename, content_type),
            timeout=settings.stt_request_timeout_seconds,
        )
        logger.info("transcription completed transcript=%r in %.2fs", transcript, time.perf_counter() - stage)

        if not transcript.strip():
            return _error(502, "Speech recognition returned no text. Try speaking more clearly.")

        stage = time.perf_counter()
        try:
            response_text = await _with_timeout(
                generate_echo_response(db, settings, transcript),
                timeout=settings.model_request_timeout_seconds,
            )
        except _StageTimeout:
            logger.exception("Echo response timed out")
            return _error(504, "Echo response generation timed out.", stage="agent")
        except Exception:
            logger.exception("Echo response generation failed")
            return _error(502, "Echo response generation failed.", stage="agent")
        logger.info("Echo response generated in %.2fs", time.perf_counter() - stage)

        stage = time.perf_counter()
        tts_provider = get_tts_provider(settings)
        logger.info("TTS started (provider=%s)", settings.tts_provider)
        out_audio = await _with_timeout(
            tts_provider.synthesize(response_text),
            timeout=settings.tts_request_timeout_seconds,
        )
        logger.info("TTS completed audio_size=%d in %.2fs", len(out_audio), time.perf_counter() - stage)
    except _StageTimeout:
        logger.exception("voice provider timed out")
        return _error(504, "Voice provider timed out.")
    except Exception:  # noqa: BLE001
        logger.exception("voice provider failed")
        return _error(502, "Voice provider failed.")

    headers = {
        "X-Echo-Transcript": _header_text(transcript),
        "X-Echo-Response": _header_text(response_text),
    }
    logger.info(
        "voice request finished ok in %.2fs (tts_out=%d bytes)",
        time.perf_counter() - pipeline_start,
        len(out_audio),
    )
    return StreamingResponse(iter([out_audio]), media_type="audio/wav", headers=headers)
