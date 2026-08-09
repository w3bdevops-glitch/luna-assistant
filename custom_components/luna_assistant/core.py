"""Luna Core for integration-internal coordination."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_PROVIDERS, CONF_ROUTES
from .latency_feedback import LatencyFeedback
from .metrics import LunaMetrics
from .provider_hub import LunaProviderHub
from .provider_hub.credentials import (
    CredentialManager,
    credentials_from_entry,
    providers_from_entry,
    routes_from_entry,
)
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
    feedback: LatencyFeedback

    @classmethod
    async def async_create(cls, hass: HomeAssistant, entry: ConfigEntry) -> LunaCore:
        """Create Prime runtime components and restore usage counters."""
        metrics = LunaMetrics()
        settings = {
            **entry.data,
            **entry.options,
            CONF_PROVIDERS: providers_from_entry(entry),
            CONF_ROUTES: routes_from_entry(entry),
        }
        credential_manager = await CredentialManager.async_create(
            hass,
            entry,
            credentials_from_entry(entry),
            settings,
        )
        providers = LunaProviderHub(hass, credential_manager, metrics)
        feedback = await LatencyFeedback.async_create(hass, entry, providers)
        core = cls(
            providers=providers,
            tools=LunaToolsHub(providers, feedback, metrics, settings),
            metrics=metrics,
            feedback=feedback,
        )
        hass.async_create_task(
            feedback.async_prepare_defaults(),
            name=f"luna_latency_defaults_{entry.entry_id}",
        )
        return core

    def diagnostics(self) -> dict:
        return {
            "architecture": "prime-v1.2",
            "provider_hub": self.providers.diagnostics(),
            "tools_hub": self.tools.diagnostics(),
            "latency_feedback": self.feedback.diagnostics(),
            "metrics": self.metrics.snapshot(),
        }
