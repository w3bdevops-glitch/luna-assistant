"""Regression checks for service-local searchable provider routes."""

from pathlib import Path

ROOT = Path(__file__).parents[1] / "custom_components" / "luna_assistant"
CONFIG = (ROOT / "config_flow.py").read_text(encoding="utf-8")
CONST = (ROOT / "const.py").read_text(encoding="utf-8")
HUB = (ROOT / "provider_hub/hub.py").read_text(encoding="utf-8")
AI_TASK = (ROOT / "ai_task.py").read_text(encoding="utf-8")
STRINGS = (ROOT / "strings.json").read_text(encoding="utf-8")

assert 'CONF_SERVICE_ROUTE = "service_route"' in CONST
assert 'CONF_IMAGE_ROUTE = "image_route"' in CONST
assert 'CONF_IMAGE_MODEL = "image_model"' in CONST
assert "multiple=True" in CONFIG
assert "mode=SelectSelectorMode.DROPDOWN" in CONFIG
assert "_save_parent_routes" in CONFIG
assert "routes_from_entry(self._get_entry())" in CONFIG
assert "route_options(capability, route)" in CONFIG
assert "if has_google" in CONFIG
assert "if has_azure" in CONFIG
assert "CONF_GOOGLE_TTS_VOICE" in HUB
assert "self._provider_order(ProviderCapability.IMAGE)" in HUB
assert "CONF_IMAGE_MODEL" in AI_TASK
assert "selected chips show priority" in STRINGS

print("Luna searchable service-route validation passed.")
