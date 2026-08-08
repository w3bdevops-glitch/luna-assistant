"""Static regression checks for the pluggable Provider Hub."""

from pathlib import Path

ROOT = Path(__file__).parents[1] / "custom_components" / "luna_assistant"
BASE = (ROOT / "provider_hub/base.py").read_text(encoding="utf-8")
REGISTRY = (ROOT / "provider_hub/registry.py").read_text(encoding="utf-8")
HUB = (ROOT / "provider_hub/hub.py").read_text(encoding="utf-8")
ENTITY = (ROOT / "entity.py").read_text(encoding="utf-8")
GOOGLE = (ROOT / "provider_hub/google.py").read_text(encoding="utf-8")
AZURE = (ROOT / "provider_hub/azure.py").read_text(encoding="utf-8")

assert "class LunaProviderAdapter(ABC)" in BASE
assert "async def async_handle_chat_log" in BASE
assert "async def async_transcribe" in BASE
assert "async def async_synthesize" in BASE
assert "class ProviderRegistry" in REGISTRY
assert "def register" in REGISTRY
assert "def providers_for" in REGISTRY
assert "self._registry.register(self.google)" in HUB
assert "self._registry.register(self.azure)" in HUB
assert "available_providers" in HUB
assert "async_handle_chat_log" in HUB
assert "class GoogleGeminiProvider(LunaProviderAdapter)" in GOOGLE
assert "class AzureSpeechProvider(LunaProviderAdapter)" in AZURE
assert "ProviderCapability.STT" in AZURE
assert "await self._provider_hub.async_handle_chat_log" in ENTITY

print("Luna Provider Hub plug-in architecture validation passed.")
