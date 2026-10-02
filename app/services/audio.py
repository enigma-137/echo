"""Lightweight WAV helpers built on the standard library only (no FFmpeg).

Target format for the ESP32 voice pipeline:
    - WAV container
    - PCM signed 16-bit little-endian
    - mono (initially), 16 kHz (configurable)
"""

from __future__ import annotations

import io
import math
import struct
import wave

HEADER_MAGIC = b"RIFF"


def decode_wav(audio_bytes: bytes) -> dict:
    """Validate that ``audio_bytes`` is a 16-bit PCM WAV and return its params.

    Raises:
        ValueError: if the bytes are not a valid 16-bit PCM WAV file.
    """
    try:
        reader = wave.open(io.BytesIO(audio_bytes), "rb")
    except (wave.Error, EOFError, OSError) as exc:
        raise ValueError(f"Not a valid WAV file: {exc}") from exc

    try:
        sample_width = reader.getsampwidth()
        if sample_width != 2:
            raise ValueError(f"Expected 16-bit PCM WAV, got sample width {sample_width} bytes")
        frame_count = reader.getnframes()
        if frame_count < 1:
            raise ValueError("WAV contains no audio frames")
        return {
            "sample_rate": reader.getframerate(),
            "channels": reader.getnchannels(),
            "frames": reader.readframes(frame_count),
        }
    finally:
        reader.close()


def _frames_to_mono_int16(frames: bytes, channels: int) -> list[int]:
    """Mix an interleaved 16-bit frame buffer down to a mono int16 sample list."""
    total_samples = len(frames) // 2
    per_channel = total_samples // max(channels, 1)
    samples: list[int] = []
    for i in range(per_channel):
        acc = 0
        for c in range(channels):
            idx = (i * channels + c) * 2
            acc += struct.unpack_from("<h", frames, idx)[0]
        samples.append(acc // channels)
    return samples


def _resample_linear(samples: list[int], src_rate: int, dst_rate: int) -> list[int]:
    """Nearest-ish linear-resample a mono int16 list to ``dst_rate``."""
    if src_rate == dst_rate:
        return list(samples)

    out_len = max(1, int(len(samples) * dst_rate / src_rate))
    if len(samples) == 1:
        return [samples[0]] * out_len

    step = (len(samples) - 1) / (out_len - 1)
    out: list[int] = []
    for o in range(out_len):
        pos = o * step
        lo = int(math.floor(pos))
        hi = min(lo + 1, len(samples) - 1)
        frac = pos - lo
        value = samples[lo] + (samples[hi] - samples[lo]) * frac
        out.append(int(round(value)))
    return out


def encode_wav(samples: list[int], sample_rate: int, channels: int = 1) -> bytes:
    """Pack a mono int16 sample list into a 16-bit PCM WAV byte string.

    ``channels`` > 1 duplicates each sample across channels (mono source assumed).
    """
    if not samples:
        samples = [0]
    if channels < 1:
        channels = 1

    if channels > 1:
        interleaved: list[int] = []
        for s in samples:
            interleaved.extend([s] * channels)
        samples = interleaved

    buf = io.BytesIO()
    with wave.open(buf, "wb") as writer:
        writer.setnchannels(channels)
        writer.setsampwidth(2)
        writer.setframerate(sample_rate)
        writer.writeframes(struct.pack(f"<{len(samples)}h", *samples))
    return buf.getvalue()


def normalize_to_format(audio_bytes: bytes, sample_rate: int, channels: int) -> bytes:
    """Decode an arbitrary 16-bit PCM WAV and re-encode it to ``sample_rate``/``channels``."""
    params = decode_wav(audio_bytes)
    mono = _frames_to_mono_int16(params["frames"], params["channels"])
    resampled = _resample_linear(mono, params["sample_rate"], sample_rate)
    return encode_wav(resampled, sample_rate, channels)
