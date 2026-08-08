"""Google Gemini provider adapter with key rotation and consumption control."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, TypeVar

from google.genai import Client, types
from google.genai.errors import APIError, ClientError
from google.genai.types import GenerateContentConfig, Part
from homeassistant.exceptions import HomeAssistantError

from ..helpers import convert_to_wav, validate_wav
from ..metrics import LunaMetrics
from .base import LunaProviderAdapter
from .credentials import CredentialLease, CredentialManager
from .models import AudioResult, ProviderCapability, ProviderError

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class _Outcome:
    value: Any
    input_units: int = 0
    output_units: int = 0


class GoogleGeminiProvider(LunaProviderAdapter):
    """Google adapter for all Prime AI capabilities."""

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

    def __init__(self, credentials: CredentialManager, metrics: LunaMetrics) -> None:
        self._credentials = credentials
        self._metrics = metrics
        self._clients: dict[str, Client] = {}

    def _client(self, lease: CredentialLease) -> Client:
        credential_id = lease.credential.credential_id
        if credential_id not in self._clients:
            self._clients[credential_id] = Client(api_key=lease.credential.secret)
        return self._clients[credential_id]

    @property
    def default_client(self) -> Client:
        """Compatibility client used only for model discovery in config UI."""
        credential = self._credentials.first(self.name)
        if credential is None:
            raise ProviderError(
                self.name, "credentials", "No Google credential configured"
            )
        if credential.credential_id not in self._clients:
            self._clients[credential.credential_id] = Client(api_key=credential.secret)
        return self._clients[credential.credential_id]

    async def _async_execute(
        self,
        *,
        capability: ProviderCapability,
        operation: str,
        callback: Callable[[Client], Awaitable[_Outcome]],
    ) -> T:
        excluded: set[str] = set()
        last_error: ProviderError | None = None
        attempts = self._credentials.failover_attempts
        for attempt in range(attempts):
            try:
                lease = await self._credentials.async_acquire(
                    self.name,
                    capability,
                    excluded=excluded,
                    failover=attempt > 0,
                )
            except ProviderError:
                if last_error is not None:
                    raise last_error
                raise
            excluded.add(lease.credential.credential_id)
            started = time.monotonic()
            try:
                outcome = await callback(self._client(lease))
            except ProviderError as err:
                last_error = err
            except (
                APIError,
                ClientError,
                ValueError,
                TypeError,
                HomeAssistantError,
            ) as err:
                status = getattr(err, "code", None)
                category = (
                    "authentication"
                    if "API_KEY_INVALID" in str(err)
                    else "rate_limit"
                    if status == 429
                    else "provider_error"
                )
                last_error = ProviderError(
                    self.name,
                    category,
                    str(err),
                    retryable=category == "rate_limit"
                    or status in {500, 502, 503, 504},
                    status=status if isinstance(status, int) else None,
                )
            else:
                await self._credentials.async_complete(
                    lease,
                    units=max(0, outcome.input_units + outcome.output_units),
                )
                self._metrics.record(
                    service=capability.value,
                    provider=self.name,
                    operation=operation,
                    started=started,
                    success=True,
                    input_units=outcome.input_units,
                    output_units=outcome.output_units,
                    failover=attempt > 0,
                )
                return outcome.value

            assert last_error is not None
            await self._credentials.async_fail(lease, last_error)
            self._metrics.record(
                service=capability.value,
                provider=self.name,
                operation=operation,
                started=started,
                success=False,
                error_category=last_error.category,
                failover=attempt > 0,
            )
            if not (
                self._credentials.auto_failover
                and (
                    last_error.retryable
                    or last_error.category in {"authentication", "authorization"}
                )
                and attempt + 1 < attempts
            ):
                raise last_error
        assert last_error is not None
        raise last_error

    async def async_handle_chat_log(
        self,
        *,
        entity,
        chat_log,
        structure=None,
        default_max_tokens: int | None = None,
        max_iterations: int = 10,
        capability: ProviderCapability = ProviderCapability.CONVERSATION,
    ) -> None:
        """Run one chat turn with a reserved Gemini key."""

        async def request(client: Client) -> _Outcome:
            usage = {"input": 0, "output": 0}

            def observe(input_tokens: int, output_tokens: int) -> None:
                usage["input"] += input_tokens
                usage["output"] += output_tokens

            await entity._async_handle_google_chat_log(
                chat_log,
                structure=structure,
                default_max_tokens=default_max_tokens,
                max_iterations=max_iterations,
                client=client,
                usage_observer=observe,
            )
            return _Outcome(None, usage["input"], usage["output"])

        await self._async_execute(
            capability=capability,
            operation="generate",
            callback=request,
        )

    async def async_generate_image(
        self, callback: Callable[[Client], Awaitable[Any]]
    ) -> Any:
        """Run an image AI Task through the same key/budget controller."""

        async def request(client: Client) -> _Outcome:
            response = await callback(client)
            usage = getattr(response, "usage_metadata", None)
            return _Outcome(
                response,
                int(getattr(usage, "prompt_token_count", 0) or 0),
                int(getattr(usage, "candidates_token_count", 0) or 0),
            )

        return await self._async_execute(
            capability=ProviderCapability.IMAGE,
            operation="generate_image",
            callback=request,
        )

    async def async_transcribe(
        self,
        *,
        audio_data: bytes,
        mime_type: str,
        prompt: str,
        model: str,
        config: GenerateContentConfig,
        **_kwargs,
    ) -> str:
        async def request(client: Client) -> _Outcome:
            response = await client.aio.models.generate_content(
                model=model,
                contents=[
                    prompt,
                    Part.from_bytes(data=audio_data, mime_type=mime_type),
                ],
                config=config,
            )
            if not response.text:
                raise ProviderError(
                    self.name, "empty_response", "Gemini STT returned no text"
                )
            usage = response.usage_metadata
            return _Outcome(
                response.text,
                int(getattr(usage, "prompt_token_count", 0) or 0),
                int(getattr(usage, "candidates_token_count", 0) or 0),
            )

        return await self._async_execute(
            capability=ProviderCapability.STT,
            operation="transcribe",
            callback=request,
        )

    async def async_synthesize(
        self,
        *,
        message: str,
        model: str,
        voice: str,
        temperature: float,
        style_prompt: str,
        **_kwargs,
    ) -> AudioResult:
        async def request(client: Client) -> _Outcome:
            config = types.GenerateContentConfig(
                temperature=temperature,
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=voice
                        )
                    )
                ),
            )
            styled_message = (
                f"{style_prompt}\n\nLeia somente o texto entre as marcas TRANSCRIÇÃO. "
                "Não leia as instruções nem as marcas.\n=== TRANSCRIÇÃO ===\n"
                f"{message}\n=== FIM DA TRANSCRIÇÃO ==="
            )
            response = await client.aio.models.generate_content(
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
                if mime_type is None:
                    mime_type = inline.mime_type
                elif (
                    inline.mime_type.replace(" ", "").lower()
                    != mime_type.replace(" ", "").lower()
                ):
                    raise ProviderError(
                        self.name,
                        "invalid_audio",
                        "Gemini returned incompatible audio parts",
                    )
                chunks.append(bytes(inline.data))
            if not chunks or mime_type is None:
                raise ProviderError(
                    self.name, "empty_audio", "Gemini TTS returned no usable audio"
                )
            wav = convert_to_wav(b"".join(chunks), mime_type)
            info = validate_wav(wav)
            usage = response.usage_metadata
            result = AudioResult(
                provider=self.name,
                format="wav",
                data=wav,
                sample_rate=info.sample_rate,
                channels=info.channels,
                bits_per_sample=info.bits_per_sample,
                voice=voice,
            )
            return _Outcome(
                result,
                int(getattr(usage, "prompt_token_count", 0) or 0),
                int(getattr(usage, "candidates_token_count", 0) or 0),
            )

        return await self._async_execute(
            capability=ProviderCapability.TTS,
            operation="synthesize",
            callback=request,
        )
