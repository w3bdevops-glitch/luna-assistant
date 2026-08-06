# Modified for Luna Assistant.
# Derived from Home Assistant Core's Google Gemini integration,
# licensed under the Apache License 2.0.

"""Audio helpers for Luna Assistant."""

from __future__ import annotations

from dataclasses import dataclass
import io
import re
from typing import Any
import wave

from homeassistant.exceptions import HomeAssistantError

from .const import LOGGER


@dataclass(frozen=True, slots=True)
class WavInfo:
    """Validated WAV metadata."""

    channels: int
    sample_width: int
    sample_rate: int
    frame_count: int

    @property
    def bits_per_sample(self) -> int:
        """Return sample width in bits."""
        return self.sample_width * 8

    @property
    def duration_seconds(self) -> float:
        """Return audio duration."""
        if self.sample_rate <= 0:
            return 0.0
        return self.frame_count / self.sample_rate


def extract_audio_parts(response: Any) -> tuple[bytes, str]:
    """Extract and concatenate every inline audio part in a Gemini response.

    Gemini normally returns one raw PCM part, but longer or future responses
    may contain multiple parts. The old implementation read only the first
    candidate and first part, which could cache an empty or incomplete file.
    """
    audio_chunks: list[bytes] = []
    selected_mime_type: str | None = None

    for candidate in getattr(response, "candidates", None) or []:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", None) or []:
            inline_data = getattr(part, "inline_data", None)
            if inline_data is None:
                continue

            mime_type = getattr(inline_data, "mime_type", None)
            data = getattr(inline_data, "data", None)

            if not isinstance(mime_type, str) or not mime_type.lower().startswith(
                "audio/"
            ):
                continue
            if isinstance(data, (bytearray, memoryview)):
                data = bytes(data)
            if not isinstance(data, bytes) or not data:
                continue

            if selected_mime_type is None:
                selected_mime_type = mime_type
            elif _normalize_mime_type(mime_type) != _normalize_mime_type(
                selected_mime_type
            ):
                raise HomeAssistantError(
                    "Gemini returned audio parts with incompatible MIME types: "
                    f"{selected_mime_type!r} and {mime_type!r}"
                )

            audio_chunks.append(data)

    if not audio_chunks or selected_mime_type is None:
        raise HomeAssistantError("Gemini TTS returned no usable inline audio data")

    return b"".join(audio_chunks), selected_mime_type


def convert_to_wav(audio_data: bytes, mime_type: str) -> bytes:
    """Return a validated WAV container for Gemini audio.

    Gemini TTS normally returns raw, little-endian PCM at 24 kHz, mono,
    16 bits. If the API already returns a WAV container, it is validated and
    passed through instead of being wrapped in a second WAV header.
    """
    if isinstance(audio_data, (bytearray, memoryview)):
        audio_data = bytes(audio_data)
    if not isinstance(audio_data, bytes):
        raise HomeAssistantError(
            f"Expected audio bytes, got {type(audio_data).__name__}"
        )
    if not audio_data:
        raise HomeAssistantError("Gemini TTS returned an empty audio payload")

    if _looks_like_wav(audio_data):
        validate_wav(audio_data)
        return audio_data

    parameters = parse_audio_mime_type(mime_type)
    channels = parameters["channels"]
    bits_per_sample = parameters["bits_per_sample"]
    sample_rate = parameters["rate"]
    sample_width = bits_per_sample // 8
    frame_size = channels * sample_width

    if len(audio_data) % frame_size:
        raise HomeAssistantError(
            "Gemini PCM payload is not aligned to complete audio frames: "
            f"{len(audio_data)} bytes for {channels} channel(s) at "
            f"{bits_per_sample} bits"
        )

    wav_buffer = io.BytesIO()
    try:
        with wave.open(wav_buffer, "wb") as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(sample_width)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_data)
    except (ValueError, wave.Error) as exc:
        raise HomeAssistantError(f"Unable to create WAV audio: {exc}") from exc

    wav_audio = wav_buffer.getvalue()
    validate_wav(wav_audio)
    return wav_audio


def validate_wav(wav_audio: bytes) -> WavInfo:
    """Validate a WAV container and return its audio metadata."""
    if not _looks_like_wav(wav_audio):
        raise HomeAssistantError("TTS output is not a RIFF/WAVE file")

    try:
        with wave.open(io.BytesIO(wav_audio), "rb") as wav_file:
            info = WavInfo(
                channels=wav_file.getnchannels(),
                sample_width=wav_file.getsampwidth(),
                sample_rate=wav_file.getframerate(),
                frame_count=wav_file.getnframes(),
            )
    except (EOFError, wave.Error) as exc:
        raise HomeAssistantError(f"Invalid WAV generated by Luna TTS: {exc}") from exc

    if info.channels not in (1, 2):
        raise HomeAssistantError(
            f"Unsupported WAV channel count: {info.channels}; expected 1 or 2"
        )
    if info.sample_width not in (1, 2, 3, 4):
        raise HomeAssistantError(
            f"Unsupported WAV sample width: {info.sample_width} bytes"
        )
    if not 8000 <= info.sample_rate <= 192000:
        raise HomeAssistantError(
            f"Invalid WAV sample rate: {info.sample_rate} Hz"
        )
    if info.frame_count <= 0:
        raise HomeAssistantError("Generated WAV contains no audio frames")

    return info


def parse_audio_mime_type(mime_type: str) -> dict[str, int]:
    """Parse raw PCM parameters from a Gemini audio MIME type."""
    if not isinstance(mime_type, str) or not mime_type.strip():
        raise HomeAssistantError("Gemini TTS returned no audio MIME type")

    parts = [part.strip() for part in mime_type.split(";") if part.strip()]
    base_type = parts[0].lower()

    if base_type in {"audio/wav", "audio/wave", "audio/x-wav"}:
        return {"bits_per_sample": 16, "rate": 24000, "channels": 1}

    raw_pcm_types = {
        "audio/pcm",
        "audio/raw",
        "audio/x-raw",
        "audio/l8",
        "audio/l16",
        "audio/l24",
        "audio/l32",
    }
    if base_type not in raw_pcm_types and not re.fullmatch(
        r"audio/l(?:8|16|24|32)", base_type
    ):
        LOGGER.warning("Received unsupported Gemini audio MIME type %s", mime_type)
        raise HomeAssistantError(f"Unsupported audio MIME type: {mime_type}")

    bits_match = re.fullmatch(r"audio/l(8|16|24|32)", base_type)
    bits_per_sample = int(bits_match.group(1)) if bits_match else 16
    rate = 24000
    channels = 1

    for parameter in parts[1:]:
        key, separator, value = parameter.partition("=")
        if not separator:
            continue
        key = key.strip().lower()
        value = value.strip().strip('"')

        try:
            if key in {"rate", "sample_rate", "samplerate"}:
                rate = int(value)
            elif key in {"channels", "channel"}:
                channels = int(value)
            elif key in {"bits", "bit_depth", "bits_per_sample"}:
                bits_per_sample = int(value)
        except ValueError as exc:
            raise HomeAssistantError(
                f"Invalid parameter in Gemini audio MIME type: {parameter}"
            ) from exc

    if bits_per_sample not in (8, 16, 24, 32):
        raise HomeAssistantError(
            f"Unsupported PCM bit depth: {bits_per_sample}"
        )
    if not 8000 <= rate <= 192000:
        raise HomeAssistantError(f"Invalid PCM sample rate: {rate}")
    if channels not in (1, 2):
        raise HomeAssistantError(
            f"Unsupported PCM channel count: {channels}"
        )

    return {
        "bits_per_sample": bits_per_sample,
        "rate": rate,
        "channels": channels,
    }


def _looks_like_wav(audio_data: bytes) -> bool:
    """Return whether bytes contain the basic RIFF/WAVE signature."""
    return (
        len(audio_data) >= 12
        and audio_data[:4] == b"RIFF"
        and audio_data[8:12] == b"WAVE"
    )


def _normalize_mime_type(mime_type: str) -> str:
    """Normalize spacing and case for MIME comparison."""
    return ";".join(
        part.strip().lower()
        for part in mime_type.split(";")
        if part.strip()
    )
