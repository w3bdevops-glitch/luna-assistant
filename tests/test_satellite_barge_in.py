"""Static validation that Assistant preserves the Satellite boundary."""

from pathlib import Path


ROOT = Path(__file__).parents[1] / "custom_components" / "luna_assistant"
CORE = (ROOT / "core.py").read_text(encoding="utf-8")
INIT = (ROOT / "__init__.py").read_text(encoding="utf-8")

assert "does not own the Assist session" in CORE
assert "microphone" in CORE
assert "wake" in CORE
assert 'SERVICE_INTERRUPT_EXTERNAL_AUDIO' in INIT
assert '"media_player",' in INIT

print("Luna Prime/Satellite boundary validation passed.")
