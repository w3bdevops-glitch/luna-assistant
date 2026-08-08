"""Microsoft Azure Speech TTS provider adapter."""

from __future__ import annotations

from html import escape
import time

from aiohttp import ClientError, ClientSession, ClientTimeout

from homeassistant.exceptions import HomeAssistantError

from ..helpers import validate_wav
from ..metrics import LunaMetrics
from .base import LunaProviderAdapter
from .models import AudioResult, ProviderCapability, ProviderError


class AzureSpeechTTSProvider(LunaProviderAdapter):
    """Azure Speech REST adapter returning pipeline-friendly WAV audio."""

    name = "azure"
    display_name = "Microsoft Azure Speech"
    capabilities = frozenset({ProviderCapability.TTS})

    def __init__(self, session: ClientSession, metrics: LunaMetrics) -> None:
        self._session = session
        self._metrics = metrics

    async def async_validate(self, *, key: str, region: str) -> None:
        """Validate an Azure Speech resource without synthesizing billable audio."""
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
                    category = (
                        "authentication"
                        if response.status in {401, 403}
                        else "provider_error"
                    )
                    raise ProviderError(
                        self.name,
                        category,
                        f"Azure Speech validation returned HTTP {response.status}",
                        retryable=response.status in {429, 500, 502, 503, 504},
                        status=response.status,
                    )
        except ProviderError:
            raise
        except (ClientError, TimeoutError) as err:
            raise ProviderError(
                self.name, "transport", str(err), retryable=True
            ) from err

    async def async_synthesize(
        self,
        *,
        message: str,
        language: str,
        voice: str,
        key: str,
        region: str,
        output_format: str,
        rate: str,
    ) -> AudioResult:
        """Synthesize speech using Azure's regional REST endpoint."""
        started = time.monotonic()
        endpoint = (
            f"https://{region.strip().lower()}.tts.speech.microsoft.com/"
            "cognitiveservices/v1"
        )
        safe_rate = rate if rate in {"-12%", "+0%", "+12%"} else "+0%"
        ssml = (
            f"<speak version='1.0' xml:lang='{escape(language)}'>"
            f"<voice name='{escape(voice)}'><prosody rate='{safe_rate}'>"
            f"{escape(message)}</prosody></voice></speak>"
        )
        headers = {
            "Ocp-Apim-Subscription-Key": key,
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": output_format,
            "User-Agent": "Luna-Assistant-Prime/1.0",
        }
        try:
            async with self._session.post(
                endpoint,
                data=ssml.encode("utf-8"),
                headers=headers,
                timeout=ClientTimeout(total=30),
            ) as response:
                audio = await response.read()
                if response.status != 200:
                    category = {
                        401: "authentication",
                        403: "authorization",
                        429: "rate_limit",
                    }.get(response.status, "provider_error")
                    detail = audio.decode("utf-8", errors="replace")[:300]
                    raise ProviderError(
                        self.name,
                        category,
                        f"Azure TTS HTTP {response.status}: {detail}",
                        retryable=response.status in {429, 500, 502, 503, 504},
                        status=response.status,
                    )
            info = validate_wav(audio)
        except ProviderError as err:
            self._metrics.record(
                service="tts", provider=self.name, operation="synthesize",
                started=started, success=False, error_category=err.category
            )
            raise
        except (ClientError, TimeoutError, ValueError, HomeAssistantError) as err:
            self._metrics.record(
                service="tts", provider=self.name, operation="synthesize",
                started=started, success=False, error_category="transport"
            )
            raise ProviderError(
                self.name, "transport", str(err), retryable=True
            ) from err

        self._metrics.record(
            service="tts", provider=self.name, operation="synthesize",
            started=started, success=True, input_units=len(message),
            output_units=len(audio)
        )
        return AudioResult(
            provider=self.name,
            format="wav",
            data=audio,
            sample_rate=info.sample_rate,
            channels=info.channels,
            bits_per_sample=info.bits_per_sample,
            voice=voice,
        )
