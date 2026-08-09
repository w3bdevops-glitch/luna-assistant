"""Microsoft Azure Speech STT and TTS provider adapter."""

from __future__ import annotations

import math
import time
from collections.abc import Awaitable, Callable
from html import escape
from typing import TypeVar
from urllib.parse import urlencode

from aiohttp import ClientError, ClientSession, ClientTimeout
from homeassistant.exceptions import HomeAssistantError

from ..helpers import validate_wav
from ..metrics import LunaMetrics
from .base import LunaProviderAdapter
from .credentials import CredentialLease, CredentialManager
from .models import AudioResult, ProviderCapability, ProviderError

T = TypeVar("T")


class AzureSpeechProvider(LunaProviderAdapter):
    """Azure regional REST adapter for short-audio STT and neural TTS."""

    name = "azure"
    display_name = "Microsoft Azure Speech"
    capabilities = frozenset({ProviderCapability.STT, ProviderCapability.TTS})

    def __init__(
        self,
        session: ClientSession,
        credentials: CredentialManager,
        metrics: LunaMetrics,
    ) -> None:
        self._session = session
        self._credentials = credentials
        self._metrics = metrics

    async def _async_execute(
        self,
        *,
        capability: ProviderCapability,
        operation: str,
        callback: Callable[[CredentialLease], Awaitable[tuple[T, int, int]]],
        provider_instance: str | None = None,
    ) -> T:
        provider_instance = self.name
        excluded: set[str] = set()
        last_error: ProviderError | None = None
        attempts = self._credentials.provider_attempts(self.name)
        for attempt in range(attempts):
            try:
                lease = await self._credentials.async_acquire(
                    provider_instance,
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
                value, input_units, output_units = await callback(lease)
            except ProviderError as err:
                last_error = err
                await self._credentials.async_fail(lease, err)
                self._metrics.record(
                    service=capability.value,
                    provider=provider_instance,
                    operation=operation,
                    started=started,
                    success=False,
                    error_category=err.category,
                    failover=attempt > 0,
                )
                if not (
                    self._credentials.auto_failover
                    and (
                        err.retryable
                        or err.category in {"authentication", "authorization"}
                    )
                    and attempt + 1 < attempts
                ):
                    raise
                continue
            await self._credentials.async_complete(
                lease, units=max(0, input_units + output_units)
            )
            self._metrics.record(
                service=capability.value,
                provider=provider_instance,
                operation=operation,
                started=started,
                success=True,
                input_units=input_units,
                output_units=output_units,
                failover=attempt > 0,
            )
            return value
        assert last_error is not None
        raise last_error

    async def async_validate(self, *, key: str, region: str) -> None:
        """Validate an Azure Speech resource without synthesizing audio."""
        endpoint = (
            f"https://{region.strip().lower()}.tts.speech.microsoft.com/"
            "cognitiveservices/voices/list"
        )
        try:
            async with self._session.get(
                endpoint,
                headers={"Ocp-Apim-Subscription-Key": key},
                timeout=ClientTimeout(total=15),
            ) as response:
                await response.read()
                if response.status != 200:
                    raise self._http_error("validation", response.status, b"")
        except ProviderError:
            raise
        except (ClientError, TimeoutError) as err:
            raise ProviderError(
                self.name, "transport", str(err), retryable=True
            ) from err

    async def async_transcribe(
        self,
        *,
        audio_data: bytes,
        mime_type: str,
        language: str,
        profanity: str = "raw",
        provider_instance: str | None = None,
        **_kwargs,
    ) -> str:
        """Transcribe Assist short audio through Azure Speech REST."""

        async def request(lease: CredentialLease) -> tuple[str, int, int]:
            region = lease.credential.region
            if not region:
                raise ProviderError(
                    self.name, "configuration", "Azure region is missing"
                )
            query = urlencode(
                {
                    "language": language or "pt-BR",
                    "format": "detailed",
                    "profanity": profanity
                    if profanity in {"masked", "removed", "raw"}
                    else "raw",
                }
            )
            endpoint = (
                f"https://{region}.stt.speech.microsoft.com/"
                f"speech/recognition/conversation/cognitiveservices/v1?{query}"
            )
            content_type = (
                "audio/ogg; codecs=opus"
                if "ogg" in mime_type.lower()
                else "audio/wav; codecs=audio/pcm; samplerate=16000"
            )
            try:
                async with self._session.post(
                    endpoint,
                    data=audio_data,
                    headers={
                        "Ocp-Apim-Subscription-Key": lease.credential.secret,
                        "Content-Type": content_type,
                        "Accept": "application/json",
                        "User-Agent": "Luna-Assistant-Prime/1.2",
                    },
                    timeout=ClientTimeout(total=45),
                ) as response:
                    payload = await response.read()
                    if response.status != 200:
                        raise self._http_error("STT", response.status, payload)
                    body = await response.json(content_type=None)
            except ProviderError:
                raise
            except (ClientError, TimeoutError, ValueError) as err:
                raise ProviderError(
                    self.name, "transport", str(err), retryable=True
                ) from err

            if body.get("RecognitionStatus") != "Success":
                status = str(body.get("RecognitionStatus", "unknown"))
                raise ProviderError(
                    self.name,
                    "no_match"
                    if status in {"NoMatch", "InitialSilenceTimeout", "BabbleTimeout"}
                    else "provider_error",
                    f"Azure STT recognition status: {status}",
                    retryable=status == "Error",
                )
            choices = body.get("NBest") or []
            transcript = str(choices[0].get("Display", "")).strip() if choices else ""
            transcript = transcript or str(body.get("DisplayText", "")).strip()
            if not transcript:
                raise ProviderError(
                    self.name, "empty_response", "Azure STT returned no text"
                )
            seconds = self._audio_seconds(audio_data, content_type)
            return transcript, seconds, 0

        return await self._async_execute(
            capability=ProviderCapability.STT,
            operation="transcribe",
            callback=request,
            provider_instance=provider_instance,
        )

    async def async_synthesize(
        self,
        *,
        message: str,
        language: str,
        voice: str,
        output_format: str,
        rate: str,
        provider_instance: str | None = None,
        **_kwargs,
    ) -> AudioResult:
        """Synthesize speech with credential rotation and character budgets."""

        async def request(lease: CredentialLease) -> tuple[AudioResult, int, int]:
            region = lease.credential.region
            if not region:
                raise ProviderError(
                    self.name, "configuration", "Azure region is missing"
                )
            endpoint = f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1"
            safe_rate = rate if rate in {"-12%", "+0%", "+12%"} else "+0%"
            ssml = (
                f"<speak version='1.0' xml:lang='{escape(language)}'>"
                f"<voice name='{escape(voice)}'><prosody rate='{safe_rate}'>"
                f"{escape(message)}</prosody></voice></speak>"
            )
            try:
                async with self._session.post(
                    endpoint,
                    data=ssml.encode("utf-8"),
                    headers={
                        "Ocp-Apim-Subscription-Key": lease.credential.secret,
                        "Content-Type": "application/ssml+xml",
                        "X-Microsoft-OutputFormat": output_format,
                        "User-Agent": "Luna-Assistant-Prime/1.2",
                    },
                    timeout=ClientTimeout(total=30),
                ) as response:
                    audio = await response.read()
                    if response.status != 200:
                        raise self._http_error("TTS", response.status, audio)
                info = validate_wav(audio)
            except ProviderError:
                raise
            except (ClientError, TimeoutError, ValueError, HomeAssistantError) as err:
                raise ProviderError(
                    self.name, "transport", str(err), retryable=True
                ) from err
            result = AudioResult(
                provider=provider_instance or self.name,
                format="wav",
                data=audio,
                sample_rate=info.sample_rate,
                channels=info.channels,
                bits_per_sample=info.bits_per_sample,
                voice=voice,
            )
            return result, len(message), 0

        return await self._async_execute(
            capability=ProviderCapability.TTS,
            operation="synthesize",
            callback=request,
            provider_instance=provider_instance,
        )

    @staticmethod
    def _audio_seconds(audio: bytes, content_type: str) -> int:
        if "wav" in content_type:
            try:
                return max(1, math.ceil(validate_wav(audio).duration_seconds))
            except HomeAssistantError:
                pass
        return max(1, math.ceil(len(audio) / 32000))

    def _http_error(self, operation: str, status: int, payload: bytes) -> ProviderError:
        category = {
            401: "authentication",
            403: "authorization",
            429: "rate_limit",
        }.get(status, "provider_error")
        detail = payload.decode("utf-8", errors="replace")[:300]
        return ProviderError(
            self.name,
            category,
            f"Azure {operation} HTTP {status}: {detail}",
            retryable=status in {429, 500, 502, 503, 504},
            status=status,
        )


# Compatibility alias for code/tests created with Prime v1.0.0.
AzureSpeechTTSProvider = AzureSpeechProvider
