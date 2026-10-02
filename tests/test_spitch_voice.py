import sys
import types
import unittest
from unittest.mock import patch

from app.config import Settings
from app.services.audio import decode_wav, encode_wav
from app.services.speech_to_text import SpitchSTTProvider, get_stt_provider, stt_configured
from app.services.text_to_speech import SpitchTTSProvider, get_tts_provider, tts_configured


class _BinaryResponse:
    async def read(self) -> bytes:
        return encode_wav([0] * 240, sample_rate=24000, channels=1)


class _Transcription:
    text = "How far, Echo?"


class _Speech:
    def __init__(self, calls: dict) -> None:
        self.calls = calls

    async def transcribe(self, **kwargs):
        self.calls["transcribe"] = kwargs
        return _Transcription()

    async def generate(self, **kwargs):
        self.calls["generate"] = kwargs
        return _BinaryResponse()


class _AsyncSpitch:
    calls: dict = {}

    def __init__(self, **kwargs) -> None:
        self.calls["client"] = kwargs
        self.speech = _Speech(self.calls)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None


class SpitchProviderTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        _AsyncSpitch.calls = {}
        self.settings = Settings(
            _env_file=None,
            stt_provider="spitch",
            tts_provider="spitch",
            spitch_api_key="test-key",
            spitch_stt_language="en",
            spitch_tts_language="en",
            spitch_tts_voice="lucy",
            audio_sample_rate=16000,
            audio_channels=1,
        )
        self.fake_module = types.SimpleNamespace(AsyncSpitch=_AsyncSpitch)

    def test_factories_and_health_configuration(self) -> None:
        self.assertIsInstance(get_stt_provider(self.settings), SpitchSTTProvider)
        self.assertIsInstance(get_tts_provider(self.settings), SpitchTTSProvider)
        self.assertTrue(stt_configured(self.settings))
        self.assertTrue(tts_configured(self.settings))

    async def test_spitch_stt_upload_contract(self) -> None:
        with patch.dict(sys.modules, {"spitch": self.fake_module}):
            text = await SpitchSTTProvider(self.settings).transcribe(
                b"RIFFaudio", "sample.wav", "audio/wav"
            )
        self.assertEqual(text, "How far, Echo?")
        self.assertEqual(_AsyncSpitch.calls["transcribe"]["language"], "en")
        self.assertEqual(
            _AsyncSpitch.calls["transcribe"]["content"],
            ("sample.wav", b"RIFFaudio", "audio/wav"),
        )

    async def test_spitch_tts_returns_configured_pcm_wav(self) -> None:
        with patch.dict(sys.modules, {"spitch": self.fake_module}):
            audio = await SpitchTTSProvider(self.settings).synthesize("Welcome home")
        request = _AsyncSpitch.calls["generate"]
        self.assertEqual(request["voice"], "lucy")
        self.assertEqual(request["language"], "en")
        self.assertEqual(request["format"], "wav")
        params = decode_wav(audio)
        self.assertEqual(params["sample_rate"], 16000)
        self.assertEqual(params["channels"], 1)


if __name__ == "__main__":
    unittest.main()
