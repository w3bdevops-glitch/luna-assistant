"""Static validation for Luna's wake-word barge-in service."""

from pathlib import Path


ROOT = Path(__file__).parents[1]
INIT_SOURCE = (ROOT / "custom_components/luna_assistant/__init__.py").read_text(
    encoding="utf-8"
)
CONST_SOURCE = (ROOT / "custom_components/luna_assistant/const.py").read_text(
    encoding="utf-8"
)

assert 'SERVICE_INTERRUPT_EXTERNAL_AUDIO = "interrupt_external_audio"' in CONST_SOURCE
assert "hass.services.has_service" in INIT_SOURCE
assert "hass.services.async_register" in INIT_SOURCE
assert '"media_player",\n            "media_stop"' in INIT_SOURCE
assert "CONF_OUTPUT_MEDIA_PLAYER" in INIT_SOURCE
assert 'target={"entity_id": sorted(targets)}' in INIT_SOURCE

print("Luna barge-in service validation passed.")
