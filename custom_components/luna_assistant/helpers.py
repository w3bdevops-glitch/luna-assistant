# Modified for Luna Assistant.
# Derived from Home Assistant Core's Google Gemini integration,
# licensed under the Apache License 2.0.

"""Audio helpers for Luna Assistant."""

from __future__ import annotations

from dataclasses import dataclass
import io
import re
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
        """Return bits per sample."""
        return self.sample_width * 8

    @property
    def duration_seconds(self) -> float:
        """Return duration in seconds."""
        return self.frame_count / self.sample_rate


def convert_to_wav(audio_data: bytes, mime_type: str) -> bytes:
    """Wrap Gemini raw PCM in WAV, or validate an existing WAV.

    This function does not resample or transcode audio. For normal Gemini PCM,
    it only writes the 44-byte WAV header and copies the PCM frames.
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

    params = parse_audio_mime_type(mime_type)
    sample_width = params["bits_per_sample"] // 8
    frame_size = params["channels"] * sample_width

    if len(audio_data) % frame_size:
        raise HomeAssistantError(
            "Gemini PCM payload is not aligned to complete audio frames: "
            f"{len(audio_data)} bytes, frame size {frame_size}"
        )

    buffer = io.BytesIO()
    try:
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(params["channels"])
            wav_file.setsampwidth(sample_width)
            wav_file.setframerate(params["rate"])
            wav_file.writeframes(audio_data)
    except (ValueError, wave.Error) as exc:
        raise HomeAssistantError(f"Unable to create WAV audio: {exc}") from exc

    wav_audio = buffer.getvalue()
    validate_wav(wav_audio)
    return wav_audio


def parse_audio_mime_type(mime_type: str) -> dict[str, int]:
    """Parse PCM parameters from a Gemini audio MIME type."""
    if not isinstance(mime_type, str) or not mime_type.strip():
        raise HomeAssistantError("Gemini TTS returned no audio MIME type")

    parts = [part.strip() for part in mime_type.split(";") if part.strip()]
    base_type = parts[0].lower()

    if base_type in {"audio/wav", "audio/wave", "audio/x-wav"}:
        return {"bits_per_sample": 16, "rate": 24000, "channels": 1}

    match = re.fullmatch(r"audio/l(8|16|24|32)", base_type)
    if match:
        bits_per_sample = int(match.group(1))
    elif base_type in {"audio/pcm", "audio/raw", "audio/x-raw"}:
        bits_per_sample = 16
    else:
        LOGGER.warning("Received unsupported Gemini audio MIME type %s", mime_type)
        raise HomeAssistantError(f"Unsupported audio MIME type: {mime_type}")

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
                f"Invalid audio MIME parameter: {parameter}"
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


def validate_wav(wav_audio: bytes) -> WavInfo:
    """Validate a RIFF/WAVE container."""
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
        raise HomeAssistantError(f"Invalid Luna TTS WAV: {exc}") from exc

    if info.channels not in (1, 2):
        raise HomeAssistantError(
            f"Unsupported WAV channel count: {info.channels}"
        )
    if info.sample_width not in (1, 2, 3, 4):
        raise HomeAssistantError(
            f"Unsupported WAV sample width: {info.sample_width}"
        )
    if not 8000 <= info.sample_rate <= 192000:
        raise HomeAssistantError(
            f"Invalid WAV sample rate: {info.sample_rate}"
        )
    if info.frame_count <= 0:
        raise HomeAssistantError("Generated WAV contains no frames")

    return info


def _looks_like_wav(audio_data: bytes) -> bool:
    """Return whether bytes have the RIFF/WAVE signature."""
    return (
        len(audio_data) >= 12
        and audio_data[:4] == b"RIFF"
        and audio_data[8:12] == b"WAVE"
    )
