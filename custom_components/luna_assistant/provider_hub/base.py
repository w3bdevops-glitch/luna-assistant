"""Stable provider plug-in contract for Luna Assistant Prime."""

from __future__ import annotations

from abc import ABC
from collections.abc import Mapping
from typing import Any

from .models import ProviderCapability, ProviderError


class LunaProviderAdapter(ABC):
    """Base class for independently pluggable Luna providers.

    A future provider is added by implementing only the methods for the
    capabilities it declares and registering one adapter in Provider Hub.
    Home Assistant entities and Luna Core remain provider-neutral.
    """

    name: str
    display_name: str
    capabilities: frozenset[ProviderCapability]

    def supports(self, capability: ProviderCapability) -> bool:
        return capability in self.capabilities

    def ensure_capability(self, capability: ProviderCapability) -> None:
        if not self.supports(capability):
            raise ProviderError(
                self.name,
                "unsupported_capability",
                f"{self.display_name} does not support {capability.value}",
            )

    async def async_handle_chat_log(
        self,
        *,
        entity: Any,
        chat_log: Any,
        structure: Any = None,
        default_max_tokens: int | None = None,
        max_iterations: int = 10,
    ) -> None:
        """Handle Conversation or AI Task data generation."""
        raise ProviderError(
            self.name,
            "not_implemented",
            f"{self.display_name} has no chat adapter",
        )

    async def async_transcribe(self, **kwargs: Any) -> str:
        """Transcribe audio."""
        raise ProviderError(
            self.name,
            "not_implemented",
            f"{self.display_name} has no STT adapter",
        )

    async def async_synthesize(self, **kwargs: Any) -> Any:
        """Synthesize speech."""
        raise ProviderError(
            self.name,
            "not_implemented",
            f"{self.display_name} has no TTS adapter",
        )

    async def async_search(self, **kwargs: Any) -> Any:
        """Search the web."""
        raise ProviderError(
            self.name,
            "not_implemented",
            f"{self.display_name} has no Search adapter",
        )

    def diagnostics(self) -> Mapping[str, Any]:
        return {
            "display_name": self.display_name,
            "capabilities": sorted(item.value for item in self.capabilities),
        }
