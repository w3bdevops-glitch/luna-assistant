"""Static validation for Luna Tools Hub."""

from pathlib import Path

ROOT = Path(__file__).parents[1] / "custom_components" / "luna_assistant"
TOOLS = (ROOT / "tools_hub.py").read_text(encoding="utf-8")
ENTITY = (ROOT / "entity.py").read_text(encoding="utf-8")

assert "class LunaToolsHub" in TOOLS
assert "GoogleSearch" in TOOLS
assert "existing or []" in TOOLS
assert "self._core.tools.build_google_tools" in ENTITY

print("Luna Tools Hub validation passed.")
