"""Luna Core for integration-internal coordination."""

from __future__ import annotations

from dataclasses import dataclass

from google.genai import Client

from homeassistant.core import HomeAssistant

from .metrics import LunaMetrics
from .provider_hub import LunaProviderHub
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
    def create(cls, hass: HomeAssistant, google_client: Client) -> "LunaCore":
        metrics = LunaMetrics()
        return cls(
            providers=LunaProviderHub(hass, google_client, metrics),
            tools=LunaToolsHub(metrics),
            metrics=metrics,
        )

    def diagnostics(self) -> dict:
        return {
            "architecture": "prime-v1",
            "provider_hub": self.providers.diagnostics(),
            "tools_hub": self.tools.diagnostics(),
            "metrics": self.metrics.snapshot(),
        }
