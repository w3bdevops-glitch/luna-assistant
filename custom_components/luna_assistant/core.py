"""Luna Core for integration-internal coordination."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .metrics import LunaMetrics
from .provider_hub import LunaProviderHub
from .provider_hub.credentials import CredentialManager, credentials_from_entry
from .tools_hub import LunaToolsHub


@dataclass(slots=True)
class LunaCore:
    """Runtime root for Prime components.

    Luna Core deliberately does not own the Assist session, microphone, wake
    word, satellite state machine or I²S audio.
    """

    providers: LunaProviderHub
    tools: LunaToolsHub
    metrics: LunaMetrics

    @classmethod
    async def async_create(cls, hass: HomeAssistant, entry: ConfigEntry) -> LunaCore:
        """Create Prime runtime components and restore usage counters."""
        metrics = LunaMetrics()
        settings = {**entry.data, **entry.options}
        credential_manager = await CredentialManager.async_create(
            hass,
            entry,
            credentials_from_entry(entry),
            settings,
        )
        return cls(
            providers=LunaProviderHub(hass, credential_manager, metrics),
            tools=LunaToolsHub(metrics),
            metrics=metrics,
        )

    def diagnostics(self) -> dict:
        return {
            "architecture": "prime-v1.1",
            "provider_hub": self.providers.diagnostics(),
            "tools_hub": self.tools.diagnostics(),
            "metrics": self.metrics.snapshot(),
        }
