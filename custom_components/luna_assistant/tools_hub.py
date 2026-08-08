"""Luna Tools Hub.

Prime v1 exposes Google Search grounding as the first Luna tool while keeping
Home Assistant function tools active in the same Gemini request.
"""

from __future__ import annotations

from typing import Any

from google.genai.types import GoogleSearch, Tool, ToolListUnion

from .metrics import LunaMetrics


class LunaToolsHub:
    """Build and account for model-native Luna tools."""

    def __init__(self, metrics: LunaMetrics) -> None:
        self._metrics = metrics
        self._search_requests = 0

    def build_google_tools(
        self, existing: ToolListUnion | None, *, enable_web_search: bool
    ) -> ToolListUnion | None:
        """Combine Home Assistant functions and Google Search grounding."""
        if not enable_web_search:
            return existing
        tools: list[Any] = list(existing or [])
        tools.append(Tool(google_search=GoogleSearch()))
        self._search_requests += 1
        return tools

    def diagnostics(self) -> dict[str, Any]:
        """Return non-sensitive Tools Hub state."""
        return {
            "provider": "google_search_grounding",
            "search_enabled_requests": self._search_requests,
            "supports_home_assistant_tools_simultaneously": True,
        }
