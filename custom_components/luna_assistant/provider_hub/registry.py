"""Provider plug-in registry."""

from __future__ import annotations

from .base import LunaProviderAdapter
from .models import ProviderCapability, ProviderError


class ProviderRegistry:
    """Register and resolve providers without coupling entities to vendors."""

    def __init__(self) -> None:
        self._adapters: dict[str, LunaProviderAdapter] = {}

    def register(self, adapter: LunaProviderAdapter) -> None:
        if adapter.name in self._adapters:
            raise ValueError(f"Provider already registered: {adapter.name}")
        self._adapters[adapter.name] = adapter

    def get(self, provider: str, capability: ProviderCapability) -> LunaProviderAdapter:
        adapter = self._adapters.get(provider)
        if adapter is None:
            raise ProviderError(
                provider, "unknown_provider", f"Unknown provider: {provider}"
            )
        adapter.ensure_capability(capability)
        return adapter

    def providers_for(self, capability: ProviderCapability) -> list[str]:
        return sorted(
            adapter.name
            for adapter in self._adapters.values()
            if adapter.supports(capability)
        )

    def diagnostics(self) -> dict:
        return {
            name: dict(adapter.diagnostics())
            for name, adapter in sorted(self._adapters.items())
        }
