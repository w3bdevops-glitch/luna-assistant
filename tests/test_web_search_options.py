"""Regression checks for the global internet-search master flag."""

from pathlib import Path

ROOT = Path(__file__).parents[1] / "custom_components" / "luna_assistant"
CONST = (ROOT / "const.py").read_text(encoding="utf-8")
CONFIG = (ROOT / "config_flow.py").read_text(encoding="utf-8")
TOOLS = (ROOT / "tools_hub.py").read_text(encoding="utf-8")
INIT = (ROOT / "__init__.py").read_text(encoding="utf-8")

assert 'CONF_SEARCH_ENABLED = "search_enabled"' in CONST
assert "DEFAULT_SEARCH_ENABLED = True" in CONST
assert "CONF_SEARCH_ENABLED" in CONFIG
assert "async_step_general" in CONFIG
assert '"route_image": "image"' in CONFIG
assert "CONF_TAVILY_SEARCH_DEPTH" in CONFIG
assert "CONF_TAVILY_MAX_RESULTS" in CONFIG
assert "not self.search_enabled" in TOOLS
assert "ProviderCapability.SEARCH" in TOOLS
assert "legacy_search_values" in INIT
assert "DEFAULT_SEARCH_ENABLED" in INIT

print("Luna global Search flag validation passed.")
