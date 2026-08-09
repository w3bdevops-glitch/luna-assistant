"""Luna tools exposed to Conversation and AI Task."""

from __future__ import annotations

from collections.abc import Mapping
from types import SimpleNamespace
from typing import Any, override

import voluptuous as vol
from homeassistant.helpers import llm

from .const import (
    CONF_SEARCH_ENABLED,
    CONF_TAVILY_MAX_RESULTS,
    CONF_TAVILY_SEARCH_DEPTH,
    DEFAULT_SEARCH_ENABLED,
    DEFAULT_TAVILY_MAX_RESULTS,
    DEFAULT_TAVILY_SEARCH_DEPTH,
)
from .latency_feedback import LatencyFeedback
from .metrics import LunaMetrics
from .provider_hub import LunaProviderHub, ProviderCapability

SEARCH_TOOL_NAME = "LunaWebSearch"


class LunaWebSearchTool(llm.Tool):
    """Home Assistant LLM tool backed by the Provider Hub Search route."""

    name = SEARCH_TOOL_NAME
    description = (
        "Pesquise na internet quando a pergunta depender de informação atual, "
        "específica ou verificável. Use os links retornados como fontes."
    )
    parameters = vol.Schema(
        {
            vol.Required("query"): str,
            vol.Optional("search_depth"): vol.In(("basic", "advanced")),
        }
    )

    def __init__(
        self,
        providers: LunaProviderHub,
        feedback: LatencyFeedback,
        options: Mapping[str, Any],
        settings: Mapping[str, Any],
    ) -> None:
        self._providers = providers
        self._feedback = feedback
        self._options = dict(options)
        self._settings = settings

    @override
    async def async_call(self, hass, tool_input: llm.ToolInput, llm_context):
        query = str(tool_input.tool_args.get("query", "")).strip()
        if not query:
            return {"error": "empty_query"}
        search_task = hass.async_create_task(
            self._providers.async_search(
                query,
                search_depth=str(
                    tool_input.tool_args.get(
                        "search_depth",
                        self._settings.get(
                            CONF_TAVILY_SEARCH_DEPTH,
                            DEFAULT_TAVILY_SEARCH_DEPTH,
                        ),
                    )
                ),
                max_results=int(
                    self._settings.get(
                        CONF_TAVILY_MAX_RESULTS, DEFAULT_TAVILY_MAX_RESULTS
                    )
                ),
            ),
            name="luna_tavily_search",
        )
        feedback_task = hass.async_create_task(
            self._feedback.async_mask_latency(
                search_task,
                self._options,
                getattr(llm_context, "device_id", None),
            ),
            name="luna_search_latency_feedback",
        )
        try:
            result = await search_task
        finally:
            await feedback_task
        return {
            "query": result.query,
            "answer": result.answer,
            "results": list(result.results),
            "provider": result.provider,
        }


class LunaSearchAPIInstance:
    """Minimal ChatLog-compatible API for AI Task without an HA LLM API."""

    def __init__(self, hass, tool: LunaWebSearchTool) -> None:
        self._hass = hass
        self.tools: list[llm.Tool] = [tool]
        self.custom_serializer = None
        self.api_prompt = "Use LunaWebSearch for current or verifiable information."

    async def async_call_tool(self, tool_input: llm.ToolInput):
        tool = next(
            (item for item in self.tools if item.name == tool_input.tool_name), None
        )
        if tool is None:
            raise ValueError(f"Unknown Luna tool: {tool_input.tool_name}")
        validated = tool.parameters(tool_input.tool_args)
        return await tool.async_call(
            self._hass,
            llm.ToolInput(
                tool_name=tool_input.tool_name,
                tool_args=validated,
                id=tool_input.id,
            ),
            SimpleNamespace(device_id=None),
        )


class LunaToolsHub:
    """Attach Luna-owned tools to the native Home Assistant LLM API instance."""

    def __init__(
        self,
        providers: LunaProviderHub,
        feedback: LatencyFeedback,
        metrics: LunaMetrics,
        settings: Mapping[str, Any],
    ) -> None:
        self._providers = providers
        self._feedback = feedback
        self._metrics = metrics
        self._settings = settings
        self._search_requests_enabled = 0

    @property
    def search_enabled(self) -> bool:
        return bool(self._settings.get(CONF_SEARCH_ENABLED, DEFAULT_SEARCH_ENABLED))

    def attach_search_tool(self, chat_log: Any, *, options: Mapping[str, Any]) -> bool:
        """Add Search once; APIInstance executes it like every other HA tool."""
        if not self.search_enabled or not self._providers.credentials.route_for(
            ProviderCapability.SEARCH
        ):
            return False
        tool = LunaWebSearchTool(
            self._providers, self._feedback, options, self._settings
        )
        api_instance = chat_log.llm_api
        if api_instance is None:
            chat_log.llm_api = LunaSearchAPIInstance(chat_log.hass, tool)
            self._search_requests_enabled += 1
            return True
        api_instance.tools[:] = [
            tool for tool in api_instance.tools if tool.name != SEARCH_TOOL_NAME
        ]
        api_instance.tools.append(tool)
        self._search_requests_enabled += 1
        return True

    def diagnostics(self) -> dict[str, Any]:
        return {
            "search_enabled": self.search_enabled,
            "search_route": self._providers.credentials.route_for(
                ProviderCapability.SEARCH
            ),
            "search_tool_name": SEARCH_TOOL_NAME,
            "requests_with_search_available": self._search_requests_enabled,
            "supports_home_assistant_tools_simultaneously": True,
        }
