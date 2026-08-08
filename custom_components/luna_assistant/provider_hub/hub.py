"""Provider selection and routing for Luna Assistant Prime."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from google.genai.types import GenerateContentConfig
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from ..const import (
    CONF_AZURE_OUTPUT_FORMAT,
    CONF_AZURE_STT_PROFANITY,
    CONF_AZURE_VOICE,
    CONF_PROVIDER,
    DEFAULT_AZURE_OUTPUT_FORMAT,
    DEFAULT_AZURE_STT_PROFANITY,
    DEFAULT_AZURE_VOICE,
    DEFAULT_PROVIDER,
    PROVIDER_GOOGLE,
)
from ..metrics import LunaMetrics
from .azure import AzureSpeechProvider
from .credentials import CredentialManager
from .google import GoogleGeminiProvider
from .models import AudioResult, ProviderCapability, ProviderError
from .registry import ProviderRegistry


class LunaProviderHub:
    """Capability-aware provider registry and router."""

    def __init__(
        self, hass: HomeAssistant, credentials: CredentialManager, metrics: LunaMetrics
    ) -> None:
        self.credentials = credentials
        self.google = GoogleGeminiProvider(credentials, metrics)
        self.azure = AzureSpeechProvider(
            async_get_clientsession(hass), credentials, metrics
        )
        self._registry = ProviderRegistry()
        self._registry.register(self.google)
        self._registry.register(self.azure)

    @property
    def google_client(self):
        """Expose Gemini's client for the Google conversation/task adapter."""
        return self.google.default_client

    def validate_capability(
        self, provider: str, capability: ProviderCapability
    ) -> None:
        """Reject unsupported provider/service combinations early."""
        self._registry.get(provider, capability)

    def available_providers(self, capability: ProviderCapability) -> list[str]:
        """Return registered providers supporting a capability."""
        return self._registry.providers_for(capability)

    def _provider_order(
        self, preferred: str, capability: ProviderCapability
    ) -> list[str]:
        """Return preferred provider followed by credentialed fallbacks."""
        order = [preferred]
        if not self.credentials.auto_failover:
            return order
        order.extend(
            provider
            for provider in self.available_providers(capability)
            if provider != preferred
            and self.credentials.has_credential(provider, capability)
        )
        return order

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
            capability=capability,
        )

    async def async_transcribe(
        self,
        *,
        options: Mapping[str, Any],
        audio_data: bytes,
        mime_type: str,
        prompt: str,
        language: str,
        model: str,
        config: GenerateContentConfig,
    ) -> str:
        provider = str(options.get(CONF_PROVIDER, DEFAULT_PROVIDER))
        last_error: ProviderError | None = None
        for candidate in self._provider_order(provider, ProviderCapability.STT):
            adapter = self._registry.get(candidate, ProviderCapability.STT)
            try:
                return await adapter.async_transcribe(
                    audio_data=audio_data,
                    mime_type=mime_type,
                    prompt=prompt,
                    model=model,
                    config=config,
                    language=language,
                    profanity=str(
                        options.get(
                            CONF_AZURE_STT_PROFANITY,
                            DEFAULT_AZURE_STT_PROFANITY,
                        )
                    ),
                )
            except ProviderError as err:
                last_error = err
                if err.category not in {
                    "authentication",
                    "authorization",
                    "budget_or_credentials_exhausted",
                    "credentials",
                    "provider_error",
                    "rate_limit",
                    "transport",
                }:
                    raise
        assert last_error is not None
        raise last_error

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
        last_error: ProviderError | None = None
        for candidate in self._provider_order(provider, ProviderCapability.TTS):
            try:
                if candidate == PROVIDER_GOOGLE:
                    google_voice = voice if provider == PROVIDER_GOOGLE else "zephyr"
                    return await self.google.async_synthesize(
                        message=message,
                        model=model,
                        voice=google_voice,
                        temperature=temperature,
                        style_prompt=style_prompt,
                    )
                pace = {"slow": "-12%", "natural": "+0%", "fast": "+12%"}.get(
                    speaking_pace, "+0%"
                )
                return await self.azure.async_synthesize(
                    message=message,
                    language=language or "pt-BR",
                    voice=str(options.get(CONF_AZURE_VOICE, DEFAULT_AZURE_VOICE)),
                    output_format=str(
                        options.get(
                            CONF_AZURE_OUTPUT_FORMAT, DEFAULT_AZURE_OUTPUT_FORMAT
                        )
                    ),
                    rate=pace,
                )
            except ProviderError as err:
                last_error = err
                if err.category not in {
                    "authentication",
                    "authorization",
                    "budget_or_credentials_exhausted",
                    "credentials",
                    "empty_audio",
                    "invalid_audio",
                    "provider_error",
                    "rate_limit",
                    "transport",
                }:
                    raise
        assert last_error is not None
        raise last_error

    async def async_validate_options(
        self, options: Mapping[str, Any], capability: ProviderCapability
    ) -> None:
        """Validate that a selected provider has a central credential."""
        provider = str(options.get(CONF_PROVIDER, DEFAULT_PROVIDER))
        self.validate_capability(provider, capability)
        if not self.credentials.has_credential(provider, capability):
            raise ProviderError(
                provider,
                "credentials",
                f"No central credential supports {provider}/{capability.value}",
            )

    async def async_generate_image(self, callback):
        """Run image AI Task through Google credential controls."""
        return await self.google.async_generate_image(callback)

    def diagnostics(self) -> dict[str, Any]:
        """Return provider matrix without credentials."""
        return {
            "providers": self._registry.diagnostics(),
            "credentials_and_consumption": self.credentials.diagnostics(),
        }
