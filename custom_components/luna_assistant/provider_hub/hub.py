"""Capability routes and failover for Luna Assistant Prime."""

from __future__ import annotations

from collections.abc import Mapping
from functools import wraps
from typing import Any

from google.genai.types import GenerateContentConfig
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from ..const import (
    CONF_AZURE_OUTPUT_FORMAT,
    CONF_AZURE_STT_PROFANITY,
    CONF_AZURE_VOICE,
    DEFAULT_AZURE_OUTPUT_FORMAT,
    DEFAULT_AZURE_STT_PROFANITY,
    DEFAULT_AZURE_VOICE,
    DEFAULT_TAVILY_MAX_RESULTS,
    DEFAULT_TAVILY_SEARCH_DEPTH,
    PROVIDER_GOOGLE,
)
from ..metrics import LunaMetrics
from .azure import AzureSpeechProvider
from .credentials import CredentialManager
from .google import GoogleGeminiProvider
from .models import AudioResult, ProviderCapability, ProviderError, SearchResult
from .registry import ProviderRegistry
from .tavily import TavilySearchProvider

FAILOVER_CATEGORIES = {
    "authentication",
    "authorization",
    "budget_or_credentials_exhausted",
    "credentials",
    "empty_audio",
    "invalid_audio",
    "provider_error",
    "rate_limit",
    "transport",
}


def _attempt_scoped(method):
    """Limit all provider/key attempts made by one routed operation."""

    @wraps(method)
    async def wrapper(self, *args, **kwargs):
        with self.credentials.call_scope():
            return await method(self, *args, **kwargs)

    return wrapper


class LunaProviderHub:
    """Route a capability, then let each provider rotate its own API keys."""

    def __init__(
        self, hass: HomeAssistant, credentials: CredentialManager, metrics: LunaMetrics
    ) -> None:
        self.credentials = credentials
        session = async_get_clientsession(hass)
        self.google = GoogleGeminiProvider(credentials, metrics)
        self.azure = AzureSpeechProvider(session, credentials, metrics)
        self.tavily = TavilySearchProvider(session, credentials, metrics)
        self._registry = ProviderRegistry()
        self._registry.register(self.google)
        self._registry.register(self.azure)
        self._registry.register(self.tavily)

    @property
    def google_client(self):
        return self.google.default_client

    def validate_capability(
        self, provider: str, capability: ProviderCapability
    ) -> None:
        self._registry.get(provider, capability)
        if not self.credentials.has_credential(provider, capability):
            raise ProviderError(
                provider,
                "credentials",
                f"No enabled key supports {provider}/{capability.value}",
            )

    def available_providers(self, capability: ProviderCapability) -> list[str]:
        return self.credentials.available_providers(capability)

    def provider_options(self, capability: ProviderCapability) -> list[dict[str, str]]:
        return [
            {
                "value": provider,
                "label": self._registry.get(provider, capability).display_name,
            }
            for provider in self.available_providers(capability)
        ]

    def adapter_for(self, provider: str, capability: ProviderCapability) -> str:
        self.validate_capability(provider, capability)
        return provider

    def _provider_order(self, capability: ProviderCapability) -> list[str]:
        route = self.credentials.route_for(capability)
        if not self.credentials.auto_failover:
            return route[:1]
        return route

    @_attempt_scoped
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
        capability = (
            ProviderCapability.AI_TASK
            if entity.subentry.subentry_type == "ai_task_data"
            else ProviderCapability.CONVERSATION
        )
        last_error: ProviderError | None = None
        for provider in self._provider_order(capability):
            adapter = self._registry.get(provider, capability)
            try:
                await adapter.async_handle_chat_log(
                    entity=entity,
                    chat_log=chat_log,
                    structure=structure,
                    default_max_tokens=default_max_tokens,
                    max_iterations=max_iterations,
                    capability=capability,
                    provider_instance=provider,
                )
                return
            except ProviderError as err:
                last_error = err
                if err.category not in FAILOVER_CATEGORIES:
                    raise
        if last_error is not None:
            raise last_error
        raise ProviderError("route", "credentials", f"No route for {capability.value}")

    @_attempt_scoped
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
        last_error: ProviderError | None = None
        for provider in self._provider_order(ProviderCapability.STT):
            adapter = self._registry.get(provider, ProviderCapability.STT)
            try:
                return await adapter.async_transcribe(
                    provider_instance=provider,
                    audio_data=audio_data,
                    mime_type=mime_type,
                    prompt=prompt,
                    model=model,
                    config=config,
                    language=language,
                    profanity=str(
                        options.get(
                            CONF_AZURE_STT_PROFANITY, DEFAULT_AZURE_STT_PROFANITY
                        )
                    ),
                )
            except ProviderError as err:
                last_error = err
                if err.category not in FAILOVER_CATEGORIES:
                    raise
        if last_error is not None:
            raise last_error
        raise ProviderError("route", "credentials", "No STT route is available")

    @_attempt_scoped
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
        last_error: ProviderError | None = None
        for provider in self._provider_order(ProviderCapability.TTS):
            try:
                if provider == PROVIDER_GOOGLE:
                    return await self.google.async_synthesize(
                        provider_instance=provider,
                        message=message,
                        model=model,
                        voice=voice or "zephyr",
                        temperature=temperature,
                        style_prompt=style_prompt,
                    )
                pace = {"slow": "-12%", "natural": "+0%", "fast": "+12%"}.get(
                    speaking_pace, "+0%"
                )
                return await self.azure.async_synthesize(
                    provider_instance=provider,
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
                if err.category not in FAILOVER_CATEGORIES:
                    raise
        if last_error is not None:
            raise last_error
        raise ProviderError("route", "credentials", "No TTS route is available")

    @_attempt_scoped
    async def async_search(
        self,
        query: str,
        *,
        search_depth: str = DEFAULT_TAVILY_SEARCH_DEPTH,
        max_results: int = DEFAULT_TAVILY_MAX_RESULTS,
    ) -> SearchResult:
        last_error: ProviderError | None = None
        for provider in self._provider_order(ProviderCapability.SEARCH):
            adapter = self._registry.get(provider, ProviderCapability.SEARCH)
            try:
                return await adapter.async_search(
                    query=query,
                    search_depth=search_depth,
                    max_results=max_results,
                )
            except ProviderError as err:
                last_error = err
                if err.category not in FAILOVER_CATEGORIES:
                    raise
        if last_error is not None:
            raise last_error
        raise ProviderError("route", "credentials", "No Search route is available")

    async def async_validate_options(
        self, options: Mapping[str, Any], capability: ProviderCapability
    ) -> None:
        route = self._provider_order(capability)
        if not route:
            raise ProviderError(
                "route", "credentials", f"No provider route supports {capability.value}"
            )
        self.validate_capability(route[0], capability)

    @_attempt_scoped
    async def async_generate_image(self, callback, provider: str = PROVIDER_GOOGLE):
        self.validate_capability(provider, ProviderCapability.IMAGE)
        return await self.google.async_generate_image(
            callback, provider_instance=provider
        )

    async def async_close(self) -> None:
        await self.credentials.async_close()

    def diagnostics(self) -> dict[str, Any]:
        return {
            "providers": self._registry.diagnostics(),
            "routes_credentials_and_consumption": self.credentials.diagnostics(),
        }
