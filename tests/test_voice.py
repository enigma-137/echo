import io
import unittest
import wave
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.services.audio import decode_wav, encode_wav


def sample_wav() -> bytes:
    return encode_wav([0] * 320, sample_rate=16000, channels=1)


class _STT:
    transcribe = AsyncMock(return_value="What can you do?")


class _TTS:
    synthesize = AsyncMock(return_value=sample_wav())


class VoiceApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client_context = TestClient(app)
        cls.client = cls.client_context.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client_context.__exit__(None, None, None)

    def test_successful_wav_request_returns_pcm_wav(self) -> None:
        with (
            patch("app.api.voice.get_stt_provider", return_value=_STT()),
            patch("app.api.voice.generate_echo_response", new=AsyncMock(return_value="I can help.")),
            patch("app.api.voice.get_tts_provider", return_value=_TTS()),
        ):
            response = self.client.post(
                "/voice", files={"audio": ("sample.wav", sample_wav(), "audio/wav")}
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "audio/wav")
        self.assertEqual(response.headers["x-echo-transcript"], "What can you do?")
        params = decode_wav(response.content)
        self.assertEqual(params["sample_rate"], 16000)
        self.assertEqual(params["channels"], 1)

    def test_missing_audio(self) -> None:
        response = self.client.post("/voice")
        self.assertEqual(response.status_code, 400)

    def test_unsupported_format(self) -> None:
        response = self.client.post(
            "/voice", files={"audio": ("sample.mp3", b"not audio", "audio/mpeg")}
        )
        self.assertEqual(response.status_code, 415)

    def test_corrupt_wav(self) -> None:
        response = self.client.post(
            "/voice", files={"audio": ("sample.wav", b"RIFFbroken", "audio/wav")}
        )
        self.assertEqual(response.status_code, 415)

    def test_empty_wav(self) -> None:
        empty = io.BytesIO()
        with wave.open(empty, "wb") as writer:
            writer.setnchannels(1)
            writer.setsampwidth(2)
            writer.setframerate(16000)
        response = self.client.post(
            "/voice", files={"audio": ("empty.wav", empty.getvalue(), "audio/wav")}
        )
        self.assertEqual(response.status_code, 415)

    def test_transcription_failure(self) -> None:
        stt = _STT()
        stt.transcribe = AsyncMock(side_effect=RuntimeError("STT down"))
        with patch("app.api.voice.get_stt_provider", return_value=stt):
            response = self.client.post(
                "/voice", files={"audio": ("sample.wav", sample_wav(), "audio/wav")}
            )
        self.assertEqual(response.status_code, 502)

    def test_agent_failure(self) -> None:
        with (
            patch("app.api.voice.get_stt_provider", return_value=_STT()),
            patch(
                "app.api.voice.generate_echo_response",
                new=AsyncMock(side_effect=RuntimeError("agent down")),
            ),
        ):
            response = self.client.post(
                "/voice", files={"audio": ("sample.wav", sample_wav(), "audio/wav")}
            )
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["stage"], "agent")

    def test_tts_failure(self) -> None:
        tts = _TTS()
        tts.synthesize = AsyncMock(side_effect=RuntimeError("TTS down"))
        with (
            patch("app.api.voice.get_stt_provider", return_value=_STT()),
            patch("app.api.voice.generate_echo_response", new=AsyncMock(return_value="Hi")),
            patch("app.api.voice.get_tts_provider", return_value=tts),
        ):
            response = self.client.post(
                "/voice", files={"audio": ("sample.wav", sample_wav(), "audio/wav")}
            )
        self.assertEqual(response.status_code, 502)

    def test_chat_regression_uses_shared_service(self) -> None:
        with patch(
            "app.api.chat.generate_echo_response", new=AsyncMock(return_value="Shared response")
        ) as generate:
            response = self.client.post("/chat", json={"message": "Hello"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"response": "Shared response"})
        generate.assert_awaited_once()

    def test_health_reports_voice_without_secrets(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertIn("voice", response.json())
        self.assertNotIn("api_key", str(response.json()).lower())


if __name__ == "__main__":
    unittest.main()
