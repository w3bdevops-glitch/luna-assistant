"""Static checks for Tavily Search credits, rotation and normalized output."""

from pathlib import Path

ROOT = Path(__file__).parents[1] / "custom_components" / "luna_assistant"
TAVILY = (ROOT / "provider_hub/tavily.py").read_text(encoding="utf-8")
HUB = (ROOT / "provider_hub/hub.py").read_text(encoding="utf-8")

assert "https://api.tavily.com/search" in TAVILY
assert "ProviderCapability.SEARCH" in TAVILY
assert "async_acquire" in TAVILY
assert 'estimated_units=2 if search_depth == "advanced" else 1' in TAVILY
assert "async_complete(lease, units=credits)" in TAVILY
assert "SearchResult(" in TAVILY
assert "async def async_search" in HUB
assert "self._provider_order(ProviderCapability.SEARCH)" in HUB

print("Luna Tavily provider validation passed.")
