"""Google Gemini provider adapter."""

from __future__ import annotations

from google.genai import Client, types
from google.genai.errors import APIError, ClientError
from google.genai.types import GenerateContentConfig, Part

from homeassistant.exceptions import HomeAssistantError

from ..helpers import convert_to_wav, validate_wav
from ..metrics import LunaMetrics
from .base import LunaProviderAdapter
from .models import AudioResult, ProviderCapability, ProviderError


class GoogleGeminiProvider(LunaProviderAdapter):
    """Google adapter for every Prime v1 AI capability."""

    name = "google"
    display_name = "Google Gemini"
    capabilities = frozenset(
        {
            ProviderCapability.AI_TASK,
            ProviderCapability.CONVERSATION,
            ProviderCapability.STT,
            ProviderCapability.TTS,
            ProviderCapability.IMAGE,
        }
    )

    def __init__(self, client: Client, metrics: LunaMetrics) -> None:
        self.client = client
        self._metrics = metrics

    async def async_handle_chat_log(
        self,
        *,
        entity,
        chat_log,
        structure=None,
        default_max_tokens: int | None = None,
        max_iterations: int = 10,
    ) -> None:
        """Run the Gemini chat engine isolated behind the adapter contract."""
        await entity._async_handle_google_chat_log(  # noqa: SLF001
            chat_log,
            structure=structure,
            default_max_tokens=default_max_tokens,
            max_iterations=max_iterations,
        )

    async def async_transcribe(
        self,
        *,
        audio_data: bytes,
        mime_type: str,
        prompt: str,
        model: str,
        config: GenerateContentConfig,
    ) -> str:
        """Transcribe audio with Gemini."""
        import time

        started = time.monotonic()
        try:
            response = await self.client.aio.models.generate_content(
                model=model,
                contents=[
                    prompt,
                    Part.from_bytes(data=audio_data, mime_type=mime_type),
                ],
                config=config,
            )
            if not response.text:
                raise ProviderError(self.name, "empty_response", "Gemini STT returned no text")
        except ProviderError:
            self._metrics.record(
                service="stt", provider=self.name, operation="transcribe",
                started=started, success=False, error_category="empty_response"
            )
            raise
        except (APIError, ClientError, ValueError) as err:
            self._metrics.record(
                service="stt", provider=self.name, operation="transcribe",
                started=started, success=False, error_category="provider_error"
            )
            raise ProviderError(
                self.name, "provider_error", str(err), retryable=True
            ) from err

        self._metrics.record(
            service="stt", provider=self.name, operation="transcribe",
            started=started, success=True, input_units=len(audio_data),
            output_units=len(response.text)
        )
        return response.text

    async def async_synthesize(
        self,
        *,
        message: str,
        model: str,
        voice: str,
        temperature: float,
        style_prompt: str,
    ) -> AudioResult:
        """Synthesize one validated WAV response with Gemini."""
        import time

        started = time.monotonic()
        config = types.GenerateContentConfig(
            temperature=temperature,
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)
                )
            ),
        )
        styled_message = (
            f"{style_prompt}\n\nLeia somente o texto entre as marcas TRANSCRIÇÃO. "
            "Não leia as instruções nem as marcas.\n=== TRANSCRIÇÃO ===\n"
            f"{message}\n=== FIM DA TRANSCRIÇÃO ==="
        )
        try:
            response = await self.client.aio.models.generate_content(
                model=model, contents=styled_message, config=config
            )
            parts = (
                response.candidates[0].content.parts
                if response.candidates
                and response.candidates[0].content
                and response.candidates[0].content.parts
                else []
            )
            chunks: list[bytes] = []
            mime_type: str | None = None
            for part in parts:
                inline = part.inline_data
                if inline is None or not inline.data or not inline.mime_type:
                    continue
                if not inline.mime_type.lower().startswith("audio/"):
                    continue
                data = bytes(inline.data)
                if mime_type is None:
                    mime_type = inline.mime_type
                elif inline.mime_type.replace(" ", "").lower() != mime_type.replace(" ", "").lower():
                    raise ProviderError(
                        self.name, "invalid_audio", "Gemini returned incompatible audio parts"
                    )
                chunks.append(data)
            if not chunks or mime_type is None:
                raise ProviderError(
                    self.name, "empty_audio", "Gemini TTS returned no usable audio"
                )
            wav = convert_to_wav(b"".join(chunks), mime_type)
            info = validate_wav(wav)
        except ProviderError as err:
            self._metrics.record(
                service="tts", provider=self.name, operation="synthesize",
                started=started, success=False, error_category=err.category
            )
            raise
        except (APIError, ClientError, ValueError, TypeError, HomeAssistantError) as err:
            self._metrics.record(
                service="tts", provider=self.name, operation="synthesize",
                started=started, success=False, error_category="provider_error"
            )
            raise ProviderError(
                self.name, "provider_error", str(err), retryable=True
            ) from err

        self._metrics.record(
            service="tts", provider=self.name, operation="synthesize",
            started=started, success=True, input_units=len(message),
            output_units=len(wav)
        )
        return AudioResult(
            provider=self.name,
            format="wav",
            data=wav,
            sample_rate=info.sample_rate,
            channels=info.channels,
            bits_per_sample=info.bits_per_sample,
            voice=voice,
        )
