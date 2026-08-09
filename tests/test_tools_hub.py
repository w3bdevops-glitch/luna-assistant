"""Static checks for Tavily Search as a native Home Assistant LLM tool."""

from pathlib import Path

ROOT = Path(__file__).parents[1] / "custom_components" / "luna_assistant"
TOOLS = (ROOT / "tools_hub.py").read_text(encoding="utf-8")
ENTITY = (ROOT / "entity.py").read_text(encoding="utf-8")

assert "class LunaToolsHub" in TOOLS
assert "class LunaWebSearchTool(llm.Tool)" in TOOLS
assert "class LunaSearchAPIInstance" in TOOLS
assert "async def async_call" in TOOLS
assert "self._providers.async_search" in TOOLS
assert "attach_search_tool" in TOOLS
assert "chat_log.llm_api" in ENTITY
assert "self._core.tools.attach_search_tool" in ENTITY
assert "GoogleSearch" not in TOOLS

print("Luna Tavily Tools Hub validation passed.")
