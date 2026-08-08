"""Provider selection and routing for Luna Assistant Prime."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from google.genai import Client
from google.genai.types import GenerateContentConfig

from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.core import HomeAssistant

from ..const import (
    CONF_AZURE_OUTPUT_FORMAT,
    CONF_AZURE_REGION,
    CONF_AZURE_SPEECH_KEY,
    CONF_AZURE_VOICE,
    CONF_PROVIDER,
    DEFAULT_AZURE_OUTPUT_FORMAT,
    DEFAULT_AZURE_REGION,
    DEFAULT_AZURE_VOICE,
    DEFAULT_PROVIDER,
    PROVIDER_AZURE,
    PROVIDER_GOOGLE,
)
from ..metrics import LunaMetrics
from .azure import AzureSpeechTTSProvider
from .google import GoogleGeminiProvider
from .models import AudioResult, ProviderCapability, ProviderError
from .registry import ProviderRegistry


class LunaProviderHub:
    """Capability-aware provider registry and router."""

    def __init__(self, hass: HomeAssistant, google_client: Client, metrics: LunaMetrics) -> None:
        self.google = GoogleGeminiProvider(google_client, metrics)
        self.azure = AzureSpeechTTSProvider(async_get_clientsession(hass), metrics)
        self._registry = ProviderRegistry()
        self._registry.register(self.google)
        self._registry.register(self.azure)

    @property
    def google_client(self) -> Client:
        """Expose Gemini's client for the Google conversation/task adapter."""
        return self.google.client

    def validate_capability(self, provider: str, capability: ProviderCapability) -> None:
        """Reject unsupported provider/service combinations early."""
        self._registry.get(provider, capability)

    def available_providers(self, capability: ProviderCapability) -> list[str]:
        """Return registered providers supporting a capability."""
        return self._registry.providers_for(capability)

    async def async_handle_chat_log(
        self,
        *,
        options: Mapping[str, Any],
        entity: Any,
        chat_log: Any,
        structure: Any = None,
        default_max_tokens: int | None = None,
        max_iterations: int = 10,
    ) -> None:
        """Route Conversation/AI Task without vendor logic in the entity."""
        provider = str(options.get(CONF_PROVIDER, DEFAULT_PROVIDER))
        capability = (
            ProviderCapability.AI_TASK
            if entity.subentry.subentry_type == "ai_task_data"
            else ProviderCapability.CONVERSATION
        )
        adapter = self._registry.get(provider, capability)
        await adapter.async_handle_chat_log(
            entity=entity,
            chat_log=chat_log,
            structure=structure,
            default_max_tokens=default_max_tokens,
            max_iterations=max_iterations,
        )

    async def async_transcribe(
        self,
        *,
        options: Mapping[str, Any],
        audio_data: bytes,
        mime_type: str,
        prompt: str,
        model: str,
        config: GenerateContentConfig,
    ) -> str:
        provider = str(options.get(CONF_PROVIDER, DEFAULT_PROVIDER))
        self.validate_capability(provider, ProviderCapability.STT)
        return await self.google.async_transcribe(
            audio_data=audio_data,
            mime_type=mime_type,
            prompt=prompt,
            model=model,
            config=config,
        )

    async def async_synthesize_tts(
        self,
        *,
        options: Mapping[str, Any],
        message: str,
        language: str,
        voice: str,
        model: str,
        temperature: float,
        style_prompt: str,
        speaking_pace: str,
    ) -> AudioResult:
        provider = str(options.get(CONF_PROVIDER, DEFAULT_PROVIDER))
        self.validate_capability(provider, ProviderCapability.TTS)
        if provider == PROVIDER_GOOGLE:
            return await self.google.async_synthesize(
                message=message,
                model=model,
                voice=voice,
                temperature=temperature,
                style_prompt=style_prompt,
            )

        key = str(options.get(CONF_AZURE_SPEECH_KEY, "")).strip()
        if not key:
            raise ProviderError(provider, "configuration", "Azure Speech key is missing")
        pace = {"slow": "-12%", "natural": "+0%", "fast": "+12%"}.get(
            speaking_pace, "+0%"
        )
        return await self.azure.async_synthesize(
            message=message,
            language=language or "pt-BR",
            voice=str(options.get(CONF_AZURE_VOICE, DEFAULT_AZURE_VOICE)) or voice,
            key=key,
            region=str(options.get(CONF_AZURE_REGION, DEFAULT_AZURE_REGION)),
            output_format=str(
                options.get(CONF_AZURE_OUTPUT_FORMAT, DEFAULT_AZURE_OUTPUT_FORMAT)
            ),
            rate=pace,
        )

    async def async_validate_tts_options(self, options: Mapping[str, Any]) -> None:
        """Validate credentials for a selected TTS adapter."""
        provider = str(options.get(CONF_PROVIDER, DEFAULT_PROVIDER))
        self.validate_capability(provider, ProviderCapability.TTS)
        if provider == PROVIDER_GOOGLE:
            return
        await self.azure.async_validate(
            key=str(options.get(CONF_AZURE_SPEECH_KEY, "")).strip(),
            region=str(options.get(CONF_AZURE_REGION, DEFAULT_AZURE_REGION)).strip(),
        )

    def diagnostics(self) -> dict[str, Any]:
        """Return provider matrix without credentials."""
        return self._registry.diagnostics()
