# Modified for Luna Assistant.
# Derived from Home Assistant Core's Google Gemini integration,
# licensed under the Apache License 2.0.

"""Config flow for Luna Assistant integration."""

import logging
from collections.abc import Mapping
from functools import partial
from typing import Any, cast, override
from uuid import uuid4

from google import genai
from google.genai.errors import APIError, ClientError
from homeassistant.config_entries import (
    SOURCE_REAUTH,
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_API_KEY, CONF_LLM_HASS_API, CONF_NAME, CONF_PROMPT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import llm
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TemplateSelector,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from requests.exceptions import Timeout
import voluptuous as vol

from .const import (
    AUDIO_OUTPUT_ATOM,
    AUDIO_OUTPUT_GOOGLE_NEST,
    AUDIO_OUTPUT_MEDIA_PLAYER,
    AZURE_PT_BR_VOICES,
    CONF_AUDIO_OUTPUT,
    CONF_AUTO_FAILOVER,
    CONF_AZURE_OUTPUT_FORMAT,
    CONF_AZURE_REGION,
    CONF_AZURE_STT_PROFANITY,
    CONF_AZURE_VOICE,
    CONF_CHAT_MODEL,
    CONF_CREDENTIAL_ACTION,
    CONF_CREDENTIAL_ID,
    CONF_CREDENTIAL_NAME,
    CONF_CREDENTIALS,
    CONF_DAILY_REQUEST_LIMIT,
    CONF_DANGEROUS_BLOCK_THRESHOLD,
    CONF_ENABLED,
    CONF_FAILOVER_ATTEMPTS,
    CONF_FAILOVER_COOLDOWN,
    CONF_HARASSMENT_BLOCK_THRESHOLD,
    CONF_HATE_BLOCK_THRESHOLD,
    CONF_IMAGE_MODEL,
    CONF_IMAGE_ROUTE,
    CONF_LATENCY_PROFILE,
    CONF_MAX_TOKENS,
    CONF_MONTHLY_REQUEST_LIMIT,
    CONF_MONTHLY_STT_SECONDS_LIMIT,
    CONF_MONTHLY_SEARCH_CREDIT_LIMIT,
    CONF_MONTHLY_TOKEN_LIMIT,
    CONF_MONTHLY_TTS_CHARACTER_LIMIT,
    CONF_OUTPUT_MEDIA_PLAYER,
    CONF_OUTPUT_TTS_ENTITY,
    CONF_PERSONALITY,
    CONF_PRIORITY,
    CONF_PROVIDER,
    CONF_PROVIDERS,
    CONF_ROUTES,
    CONF_SERVICE_ROUTE,
    CONF_SEARCH_ENABLED,
    CONF_PROVIDER_ACTION,
    CONF_PROVIDER_ADAPTER,
    CONF_PROVIDER_CAPABILITIES,
    CONF_PROVIDER_INSTANCE_ID,
    CONF_PROVIDER_INSTANCE_NAME,
    CONF_PROVIDER_INSTANCES,
    CONF_PROVIDER_LIMITS,
    CONF_RECOMMENDED,
    CONF_RESPONSE_LENGTH,
    CONF_ROTATION_STRATEGY,
    CONF_SEXUAL_BLOCK_THRESHOLD,
    CONF_SPEAKING_PACE,
    CONF_TAVILY_MAX_RESULTS,
    CONF_TAVILY_SEARCH_DEPTH,
    CONF_LATENCY_FEEDBACK_ENABLED,
    CONF_LATENCY_FEEDBACK_DELAY_MS,
    CONF_LATENCY_PHRASES,
    CONF_TEMPERATURE,
    CONF_THINKING_BUDGET,
    CONF_THINKING_LEVEL,
    CONF_TOP_K,
    CONF_TOP_P,
    CONF_VOICE_MOOD,
    CONF_GOOGLE_TTS_VOICE,
    DEFAULT_AI_TASK_NAME,
    DEFAULT_AUDIO_OUTPUT,
    DEFAULT_AZURE_OUTPUT_FORMAT,
    DEFAULT_AZURE_REGION,
    DEFAULT_AZURE_STT_PROFANITY,
    DEFAULT_AZURE_VOICE,
    DEFAULT_CONVERSATION_NAME,
    DEFAULT_FAILOVER_ATTEMPTS,
    DEFAULT_FAILOVER_COOLDOWN,
    DEFAULT_LATENCY_PROFILE,
    DEFAULT_PERSONALITY,
    DEFAULT_SEARCH_ENABLED,
    DEFAULT_LATENCY_FEEDBACK_DELAY_MS,
    DEFAULT_LATENCY_PHRASES,
    DEFAULT_RESPONSE_LENGTH,
    DEFAULT_ROTATION_STRATEGY,
    DEFAULT_GOOGLE_TTS_VOICE,
    DEFAULT_SPEAKING_PACE,
    DEFAULT_STT_NAME,
    DEFAULT_STT_PROMPT,
    DEFAULT_TAVILY_MAX_RESULTS,
    DEFAULT_TAVILY_SEARCH_DEPTH,
    DEFAULT_TITLE,
    DEFAULT_TTS_NAME,
    DEFAULT_TTS_STYLE_PROMPT,
    DEFAULT_VOICE_MOOD,
    DOMAIN,
    PROVIDER_AZURE,
    PROVIDER_CAPABILITIES,
    PROVIDER_DISPLAY_NAMES,
    PROVIDER_GOOGLE,
    PROVIDER_TAVILY,
    GOOGLE_TTS_VOICES,
    RECOMMENDED_AI_TASK_OPTIONS,
    RECOMMENDED_CHAT_MODEL,
    RECOMMENDED_CONVERSATION_OPTIONS,
    RECOMMENDED_HARM_BLOCK_THRESHOLD,
    RECOMMENDED_IMAGE_MODEL,
    RECOMMENDED_MAX_TOKENS,
    RECOMMENDED_STT_MODEL,
    RECOMMENDED_STT_OPTIONS,
    RECOMMENDED_TEMPERATURE,
    RECOMMENDED_THINKING_BUDGET,
    RECOMMENDED_THINKING_LEVEL,
    RECOMMENDED_TOP_K,
    RECOMMENDED_TOP_P,
    RECOMMENDED_TTS_MODEL,
    RECOMMENDED_TTS_OPTIONS,
    ROTATION_STRATEGIES,
    TIMEOUT_MILLIS,
)
from .provider_hub import ProviderCapability, ProviderError
from .provider_hub.credentials import (
    credentials_from_entry,
    provider_instances_from_entry,
    providers_from_entry,
    routes_from_entry,
)

_LOGGER = logging.getLogger(__name__)

STEP_API_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> None:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    client = await hass.async_add_executor_job(
        partial(genai.Client, api_key=data[CONF_API_KEY])
    )
    await client.aio.models.list(
        config={
            "http_options": {
                "timeout": TIMEOUT_MILLIS,
            },
            "query_base": True,
        }
    )


class LunaAssistantConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the provider-aware Luna Assistant Prime config flow."""

    VERSION = 2
    MINOR_VERSION = 11

    async def async_step_api(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match(user_input)
            try:
                await validate_input(self.hass, user_input)
            except (APIError, Timeout) as err:
                if isinstance(err, ClientError) and "API_KEY_INVALID" in str(err):
                    errors["base"] = "invalid_auth"
                else:
                    errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if self.source == SOURCE_REAUTH:
                    reauth_entry = self._get_reauth_entry()
                    credentials = credentials_from_entry(reauth_entry)
                    for credential in credentials:
                        if credential.get("provider") == PROVIDER_GOOGLE:
                            credential["api_key"] = user_input[CONF_API_KEY]
                            break
                    updated_data = {
                        **reauth_entry.data,
                        **user_input,
                        CONF_CREDENTIALS: credentials,
                    }
                    if CONF_CREDENTIALS in reauth_entry.options:
                        self.hass.config_entries.async_update_entry(
                            reauth_entry,
                            options={
                                **reauth_entry.options,
                                CONF_CREDENTIALS: credentials,
                            },
                        )
                    return self.async_update_reload_and_abort(
                        reauth_entry,
                        data=updated_data,
                    )
                return self.async_create_entry(
                    title=DEFAULT_TITLE,
                    data={
                        **user_input,
                        CONF_CREDENTIALS: [
                            {
                                "id": "google-primary",
                                "provider": PROVIDER_GOOGLE,
                                "name": "Google principal",
                                "api_key": user_input[CONF_API_KEY],
                                "priority": 1,
                                "enabled": True,
                            }
                        ],
                    },
                    subentries=[
                        {
                            "subentry_type": "conversation",
                            "data": RECOMMENDED_CONVERSATION_OPTIONS,
                            "title": DEFAULT_CONVERSATION_NAME,
                            "unique_id": None,
                        },
                        {
                            "subentry_type": "tts",
                            "data": RECOMMENDED_TTS_OPTIONS,
                            "title": DEFAULT_TTS_NAME,
                            "unique_id": None,
                        },
                        {
                            "subentry_type": "ai_task_data",
                            "data": RECOMMENDED_AI_TASK_OPTIONS,
                            "title": DEFAULT_AI_TASK_NAME,
                            "unique_id": None,
                        },
                        {
                            "subentry_type": "stt",
                            "data": RECOMMENDED_STT_OPTIONS,
                            "title": DEFAULT_STT_NAME,
                            "unique_id": None,
                        },
                    ],
                )
        return self.async_show_form(
            step_id="api",
            data_schema=STEP_API_DATA_SCHEMA,
            description_placeholders={
                "api_key_url": "https://aistudio.google.com/app/apikey"
            },
            errors=errors,
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        return await self.async_step_api()

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle configuration by re-auth."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is not None:
            return await self.async_step_api()

        reauth_entry = self._get_reauth_entry()
        return self.async_show_form(
            step_id="reauth_confirm",
            description_placeholders={
                CONF_NAME: reauth_entry.title,
                CONF_API_KEY: reauth_entry.data.get(CONF_API_KEY, ""),
            },
        )

    @classmethod
    @callback
    @override
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this integration."""
        return {
            "conversation": LLMSubentryFlowHandler,
            "stt": LLMSubentryFlowHandler,
            "tts": LLMSubentryFlowHandler,
            "ai_task_data": LLMSubentryFlowHandler,
        }

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the central credentials and consumption options flow."""
        return LunaAssistantOptionsFlow()


class _LegacyProviderInstanceOptionsFlow(OptionsFlow):
    """Manage provider instances and their isolated credential pools."""

    _ADAPTER_CAPABILITIES = {
        PROVIDER_GOOGLE: ("ai_task", "conversation", "image", "stt", "tts"),
        PROVIDER_AZURE: ("stt", "tts"),
    }

    def _ensure_state(self) -> None:
        if hasattr(self, "_working_options"):
            return
        self._working_options = dict(self.config_entry.options)
        self._provider_instances = provider_instances_from_entry(self.config_entry)
        self._editing_provider_id: str | None = None
        self._editing_id: str | None = None

    def _provider(self) -> dict[str, Any]:
        return next(
            item
            for item in self._provider_instances
            if item["id"] == self._editing_provider_id
        )

    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
        self._ensure_state()
        return self.async_show_menu(
            step_id="init",
            menu_options=["general", "provider_instances", "save"],
        )

    async def async_step_general(self, user_input=None) -> ConfigFlowResult:
        self._ensure_state()
        if user_input is not None:
            self._working_options.update(user_input)
            return await self.async_step_init()
        return self.async_show_form(
            step_id="general",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_AUTO_FAILOVER,
                        default=self._working_options.get(CONF_AUTO_FAILOVER, True),
                    ): bool,
                    vol.Required(
                        CONF_FAILOVER_ATTEMPTS,
                        default=self._working_options.get(
                            CONF_FAILOVER_ATTEMPTS, DEFAULT_FAILOVER_ATTEMPTS
                        ),
                    ): NumberSelector(NumberSelectorConfig(min=0, max=100, step=1)),
                    vol.Required(
                        CONF_FAILOVER_COOLDOWN,
                        default=self._working_options.get(
                            CONF_FAILOVER_COOLDOWN, DEFAULT_FAILOVER_COOLDOWN
                        ),
                    ): NumberSelector(NumberSelectorConfig(min=10, max=86400, step=10)),
                }
            ),
        )

    async def async_step_provider_instances(self, user_input=None) -> ConfigFlowResult:
        self._ensure_state()
        options = [SelectOptionDict(value="__add__", label="+ Provider")]
        options.extend(
            SelectOptionDict(
                value=item["id"],
                label=(
                    f"{item.get('name', item['id'])} · {item.get('adapter')} "
                    f"· P{item.get('priority', 100)} "
                    f"· {'ON' if item.get('enabled', True) else 'OFF'}"
                ),
            )
            for item in self._provider_instances
        )
        if user_input is not None:
            selected = str(user_input[CONF_PROVIDER_INSTANCE_ID])
            if selected == "__add__":
                return await self.async_step_add_provider()
            self._editing_provider_id = selected
            action = str(user_input[CONF_PROVIDER_ACTION])
            if action == "credentials":
                return await self.async_step_provider_credentials()
            if action == "delete":
                return await self.async_step_delete_provider()
            return await self.async_step_edit_provider()
        return self.async_show_form(
            step_id="provider_instances",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PROVIDER_INSTANCE_ID): SelectSelector(
                        SelectSelectorConfig(options=options)
                    ),
                    vol.Required(CONF_PROVIDER_ACTION, default="edit"): SelectSelector(
                        SelectSelectorConfig(options=["edit", "credentials", "delete"])
                    ),
                }
            ),
            description_placeholders={
                "provider_count": str(len(self._provider_instances))
            },
        )

    async def async_step_add_provider(self, user_input=None) -> ConfigFlowResult:
        self._ensure_state()
        if user_input is not None:
            adapter = str(user_input[CONF_PROVIDER_ADAPTER])
            instance = {
                "id": uuid4().hex,
                "name": str(user_input[CONF_PROVIDER_INSTANCE_NAME]).strip(),
                "adapter": adapter,
                "enabled": True,
                "priority": len(self._provider_instances) + 1,
                "capabilities": list(self._ADAPTER_CAPABILITIES[adapter]),
                "rotation_strategy": DEFAULT_ROTATION_STRATEGY,
                "max_attempts": 0,
                "cooldown_seconds": DEFAULT_FAILOVER_COOLDOWN,
                "limits": {},
                "credentials": [],
            }
            self._provider_instances.append(instance)
            self._editing_provider_id = instance["id"]
            return await self.async_step_edit_provider()
        return self.async_show_form(
            step_id="add_provider",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PROVIDER_INSTANCE_NAME): str,
                    vol.Required(
                        CONF_PROVIDER_ADAPTER, default=PROVIDER_GOOGLE
                    ): SelectSelector(
                        SelectSelectorConfig(options=[PROVIDER_GOOGLE, PROVIDER_AZURE])
                    ),
                }
            ),
        )

    async def async_step_edit_provider(self, user_input=None) -> ConfigFlowResult:
        self._ensure_state()
        current = self._provider()
        adapter = str(current["adapter"])
        allowed = set(self._ADAPTER_CAPABILITIES[adapter])
        errors: dict[str, str] = {}
        if user_input is not None:
            capabilities = {
                str(item) for item in user_input[CONF_PROVIDER_CAPABILITIES]
            }
            if not capabilities or not capabilities.issubset(allowed):
                errors[CONF_PROVIDER_CAPABILITIES] = "invalid_capabilities"
            if not errors:
                limits = {
                    "daily_request_limit": int(user_input[CONF_DAILY_REQUEST_LIMIT]),
                    "monthly_request_limit": int(
                        user_input[CONF_MONTHLY_REQUEST_LIMIT]
                    ),
                    "monthly_unit_limits": (
                        {"*": int(user_input[CONF_MONTHLY_TOKEN_LIMIT])}
                        if adapter == PROVIDER_GOOGLE
                        else {
                            "tts": int(user_input[CONF_MONTHLY_TTS_CHARACTER_LIMIT]),
                            "stt": int(user_input[CONF_MONTHLY_STT_SECONDS_LIMIT]),
                        }
                    ),
                }
                current.update(
                    {
                        "name": str(user_input[CONF_PROVIDER_INSTANCE_NAME]).strip(),
                        "enabled": bool(user_input[CONF_ENABLED]),
                        "priority": int(user_input[CONF_PRIORITY]),
                        "capabilities": sorted(capabilities),
                        "rotation_strategy": user_input[CONF_ROTATION_STRATEGY],
                        "max_attempts": int(user_input[CONF_FAILOVER_ATTEMPTS]),
                        "cooldown_seconds": int(user_input[CONF_FAILOVER_COOLDOWN]),
                        "limits": limits,
                    }
                )
                return await self.async_step_provider_instances()

        limits = current.get("limits", {})
        unit_limits = limits.get("monthly_unit_limits", {})
        schema: dict[Any, Any] = {
            vol.Required(
                CONF_PROVIDER_INSTANCE_NAME, default=current.get("name", "Provider")
            ): str,
            vol.Required(CONF_ENABLED, default=current.get("enabled", True)): bool,
            vol.Required(
                CONF_PRIORITY, default=current.get("priority", 100)
            ): NumberSelector(NumberSelectorConfig(min=1, max=1000, step=1)),
            vol.Required(
                CONF_PROVIDER_CAPABILITIES,
                default=current.get("capabilities", list(allowed)),
            ): SelectSelector(
                SelectSelectorConfig(options=sorted(allowed), multiple=True)
            ),
            vol.Required(
                CONF_ROTATION_STRATEGY,
                default=current.get("rotation_strategy", DEFAULT_ROTATION_STRATEGY),
            ): SelectSelector(SelectSelectorConfig(options=list(ROTATION_STRATEGIES))),
            vol.Required(
                CONF_FAILOVER_ATTEMPTS, default=current.get("max_attempts", 0)
            ): NumberSelector(NumberSelectorConfig(min=0, max=100, step=1)),
            vol.Required(
                CONF_FAILOVER_COOLDOWN,
                default=current.get("cooldown_seconds", DEFAULT_FAILOVER_COOLDOWN),
            ): NumberSelector(NumberSelectorConfig(min=10, max=86400, step=10)),
            vol.Optional(
                CONF_DAILY_REQUEST_LIMIT,
                default=limits.get("daily_request_limit", 0),
            ): NumberSelector(NumberSelectorConfig(min=0, max=1000000, step=1)),
            vol.Optional(
                CONF_MONTHLY_REQUEST_LIMIT,
                default=limits.get("monthly_request_limit", 0),
            ): NumberSelector(NumberSelectorConfig(min=0, max=10000000, step=1)),
        }
        if adapter == PROVIDER_GOOGLE:
            schema[
                vol.Optional(CONF_MONTHLY_TOKEN_LIMIT, default=unit_limits.get("*", 0))
            ] = NumberSelector(NumberSelectorConfig(min=0, max=1000000000, step=1000))
        else:
            schema.update(
                {
                    vol.Optional(
                        CONF_MONTHLY_TTS_CHARACTER_LIMIT,
                        default=unit_limits.get("tts", 0),
                    ): NumberSelector(
                        NumberSelectorConfig(min=0, max=1000000000, step=1000)
                    ),
                    vol.Optional(
                        CONF_MONTHLY_STT_SECONDS_LIMIT,
                        default=unit_limits.get("stt", 0),
                    ): NumberSelector(
                        NumberSelectorConfig(min=0, max=100000000, step=60)
                    ),
                }
            )
        return self.async_show_form(
            step_id="edit_provider",
            data_schema=vol.Schema(schema),
            errors=errors,
            description_placeholders={"adapter": adapter},
        )

    async def async_step_delete_provider(self, user_input=None) -> ConfigFlowResult:
        self._ensure_state()
        current = self._provider()
        if user_input is not None and user_input.get("confirm") is True:
            self._provider_instances = [
                item
                for item in self._provider_instances
                if item["id"] != self._editing_provider_id
            ]
            self._editing_provider_id = None
            return await self.async_step_provider_instances()
        return self.async_show_form(
            step_id="delete_provider",
            data_schema=vol.Schema({vol.Required("confirm", default=False): bool}),
            description_placeholders={"provider_name": current.get("name", "")},
        )

    async def async_step_provider_credentials(
        self, user_input=None
    ) -> ConfigFlowResult:
        self._ensure_state()
        provider = self._provider()
        credentials = provider.setdefault("credentials", [])
        options = [SelectOptionDict(value="__add__", label="+ API key")]
        options.extend(
            SelectOptionDict(
                value=item["id"],
                label=(
                    f"{item.get('name', item['id'])} · P{item.get('priority', 100)} "
                    f"· {'ON' if item.get('enabled', True) else 'OFF'}"
                ),
            )
            for item in credentials
        )
        if user_input is not None:
            action = str(user_input[CONF_CREDENTIAL_ACTION])
            if action == "back":
                return await self.async_step_provider_instances()
            selected = str(user_input[CONF_CREDENTIAL_ID])
            if selected == "__add__":
                return await self.async_step_add_credential()
            self._editing_id = selected
            if action == "delete":
                return await self.async_step_delete_credential()
            return await self.async_step_edit_credential()
        return self.async_show_form(
            step_id="provider_credentials",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CREDENTIAL_ID): SelectSelector(
                        SelectSelectorConfig(options=options)
                    ),
                    vol.Required(
                        CONF_CREDENTIAL_ACTION, default="edit"
                    ): SelectSelector(
                        SelectSelectorConfig(options=["edit", "delete", "back"])
                    ),
                }
            ),
            description_placeholders={
                "provider_name": str(provider.get("name", "")),
                "credential_count": str(len(credentials)),
            },
        )

    async def async_step_add_credential(self, user_input=None) -> ConfigFlowResult:
        return await self._async_credential_form(user_input)

    async def async_step_edit_credential(self, user_input=None) -> ConfigFlowResult:
        credentials = self._provider().setdefault("credentials", [])
        current = next(item for item in credentials if item["id"] == self._editing_id)
        return await self._async_credential_form(user_input, current=current)

    async def async_step_delete_credential(self, user_input=None) -> ConfigFlowResult:
        provider = self._provider()
        credentials = provider.setdefault("credentials", [])
        current = next(item for item in credentials if item["id"] == self._editing_id)
        if user_input is not None and user_input.get("confirm") is True:
            provider["credentials"] = [
                item for item in credentials if item["id"] != self._editing_id
            ]
            self._editing_id = None
            return await self.async_step_provider_credentials()
        return self.async_show_form(
            step_id="delete_credential",
            data_schema=vol.Schema({vol.Required("confirm", default=False): bool}),
            description_placeholders={"credential_name": current.get("name", "")},
        )

    async def _async_credential_form(
        self, user_input, *, current: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        provider = self._provider()
        adapter = str(provider["adapter"])
        credentials = provider.setdefault("credentials", [])
        current = current or {}
        errors: dict[str, str] = {}
        if user_input is not None:
            secret = str(user_input.get(CONF_API_KEY, "")).strip() or str(
                current.get("api_key", "")
            )
            region = str(user_input.get(CONF_AZURE_REGION, "")).strip().lower()
            if not secret:
                errors[CONF_API_KEY] = "key_required"
            if adapter == PROVIDER_AZURE and not region:
                errors[CONF_AZURE_REGION] = "azure_region_required"
            duplicate = any(
                item.get("id") != current.get("id")
                and str(item.get("api_key", "")).strip() == secret
                and (
                    adapter == PROVIDER_GOOGLE
                    or str(item.get("region", "")).strip().lower() == region
                )
                for item in credentials
            )
            if secret and duplicate:
                errors[CONF_API_KEY] = "duplicate_credential"
            if not errors:
                try:
                    if adapter == PROVIDER_GOOGLE:
                        await validate_input(self.hass, {CONF_API_KEY: secret})
                    else:
                        azure = self.config_entry.runtime_data.providers.azure
                        await azure.async_validate(key=secret, region=region)
                except (APIError, ProviderError, Timeout):
                    errors["base"] = "invalid_auth"
            if not errors:
                item = {
                    "id": current.get("id", uuid4().hex),
                    "name": user_input[CONF_CREDENTIAL_NAME],
                    "api_key": secret,
                    "region": region if adapter == PROVIDER_AZURE else None,
                    "enabled": bool(user_input[CONF_ENABLED]),
                    "priority": int(user_input[CONF_PRIORITY]),
                    "daily_request_limit": int(user_input[CONF_DAILY_REQUEST_LIMIT]),
                    "monthly_request_limit": int(
                        user_input[CONF_MONTHLY_REQUEST_LIMIT]
                    ),
                    "monthly_unit_limits": (
                        {"*": int(user_input[CONF_MONTHLY_TOKEN_LIMIT])}
                        if adapter == PROVIDER_GOOGLE
                        else {
                            "tts": int(user_input[CONF_MONTHLY_TTS_CHARACTER_LIMIT]),
                            "stt": int(user_input[CONF_MONTHLY_STT_SECONDS_LIMIT]),
                        }
                    ),
                }
                provider["credentials"] = [
                    existing
                    for existing in credentials
                    if existing.get("id") != item["id"]
                ] + [item]
                self._editing_id = None
                return await self.async_step_provider_credentials()

        limits = current.get("monthly_unit_limits", {})
        schema: dict[Any, Any] = {
            vol.Required(
                CONF_CREDENTIAL_NAME,
                default=current.get(
                    "name", "Google key" if adapter == PROVIDER_GOOGLE else "Azure key"
                ),
            ): str,
            vol.Optional(CONF_API_KEY): TextSelector(
                TextSelectorConfig(type=TextSelectorType.PASSWORD)
            ),
            vol.Required(CONF_ENABLED, default=current.get("enabled", True)): bool,
            vol.Required(
                CONF_PRIORITY, default=current.get("priority", 100)
            ): NumberSelector(NumberSelectorConfig(min=1, max=1000, step=1)),
            vol.Optional(
                CONF_DAILY_REQUEST_LIMIT,
                default=current.get("daily_request_limit", 0),
            ): NumberSelector(NumberSelectorConfig(min=0, max=1000000, step=1)),
            vol.Optional(
                CONF_MONTHLY_REQUEST_LIMIT,
                default=current.get("monthly_request_limit", 0),
            ): NumberSelector(NumberSelectorConfig(min=0, max=10000000, step=1)),
        }
        if adapter == PROVIDER_GOOGLE:
            schema[
                vol.Optional(CONF_MONTHLY_TOKEN_LIMIT, default=limits.get("*", 0))
            ] = NumberSelector(NumberSelectorConfig(min=0, max=1000000000, step=1000))
        else:
            schema.update(
                {
                    vol.Required(
                        CONF_AZURE_REGION,
                        default=current.get("region", DEFAULT_AZURE_REGION),
                    ): str,
                    vol.Optional(
                        CONF_MONTHLY_TTS_CHARACTER_LIMIT,
                        default=limits.get("tts", 0),
                    ): NumberSelector(
                        NumberSelectorConfig(min=0, max=1000000000, step=1000)
                    ),
                    vol.Optional(
                        CONF_MONTHLY_STT_SECONDS_LIMIT,
                        default=limits.get("stt", 0),
                    ): NumberSelector(
                        NumberSelectorConfig(min=0, max=100000000, step=60)
                    ),
                }
            )
        return self.async_show_form(
            step_id="edit_credential" if current else "add_credential",
            data_schema=vol.Schema(schema),
            errors=errors,
            description_placeholders={"provider_name": provider.get("name", "")},
        )

    async def async_step_save(self, user_input=None) -> ConfigFlowResult:
        self._ensure_state()
        has_google = any(
            instance.get("adapter") == PROVIDER_GOOGLE
            and instance.get("enabled", True)
            and any(
                credential.get("enabled", True)
                and str(credential.get("api_key", "")).strip()
                for credential in instance.get("credentials", [])
            )
            for instance in self._provider_instances
        )
        if not has_google:
            return await self.async_step_google_required()
        self._working_options[CONF_PROVIDER_INSTANCES] = self._provider_instances
        self._working_options.pop(CONF_CREDENTIALS, None)
        self._working_options.pop(CONF_PROVIDER_LIMITS, None)
        return self.async_create_entry(title="", data=self._working_options)

    async def async_step_google_required(self, user_input=None) -> ConfigFlowResult:
        if user_input is not None:
            return await self.async_step_init()
        return self.async_show_form(
            step_id="google_required", data_schema=vol.Schema({})
        )


class LunaAssistantOptionsFlow(OptionsFlow):
    """Manage one provider per technology, ordered routes and Search feedback."""

    def _ensure_state(self) -> None:
        if hasattr(self, "_working_options"):
            return
        self._working_options = dict(self.config_entry.options)
        self._providers = providers_from_entry(self.config_entry)
        self._routes = routes_from_entry(self.config_entry)
        self._editing_provider = PROVIDER_GOOGLE
        self._editing_id: str | None = None

    def _provider(self) -> dict[str, Any]:
        return self._providers[self._editing_provider]

    @staticmethod
    def _normalize_route(value: Any) -> list[str]:
        """Normalize selector values while preserving the selected priority."""
        values = value if isinstance(value, (list, tuple)) else [value]
        route: list[str] = []
        for item in values:
            provider = str(item).strip().lower()
            if provider and provider not in route:
                route.append(provider)
        return route

    def _route_options(
        self, capability: str, current: list[str] | None = None
    ) -> list[SelectOptionDict]:
        """Return enabled and compatible providers for a searchable selector."""
        current = current or []
        options: list[SelectOptionDict] = []
        for provider, supported in PROVIDER_CAPABILITIES.items():
            config = self._providers.get(provider, {})
            enabled = bool(config.get("enabled", True))
            configured = capability in config.get("capabilities", supported)
            if enabled and configured and capability in supported:
                options.append(
                    SelectOptionDict(
                        value=provider, label=PROVIDER_DISPLAY_NAMES[provider]
                    )
                )
            elif provider in current:
                options.append(
                    SelectOptionDict(
                        value=provider,
                        label=f"{PROVIDER_DISPLAY_NAMES[provider]} ⚠",
                    )
                )
        return options

    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
        self._ensure_state()
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "general",
                "providers",
                "routes",
                "latency_feedback",
                "generate_latency_audio",
                "preview_latency_audio",
                "save",
            ],
        )

    async def async_step_general(self, user_input=None) -> ConfigFlowResult:
        self._ensure_state()
        if user_input is not None:
            self._working_options.update(user_input)
            return await self.async_step_init()
        return self.async_show_form(
            step_id="general",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SEARCH_ENABLED,
                        default=self._working_options.get(
                            CONF_SEARCH_ENABLED, DEFAULT_SEARCH_ENABLED
                        ),
                    ): bool,
                    vol.Required(
                        CONF_AUTO_FAILOVER,
                        default=self._working_options.get(CONF_AUTO_FAILOVER, True),
                    ): bool,
                    vol.Required(
                        CONF_FAILOVER_ATTEMPTS,
                        default=self._working_options.get(
                            CONF_FAILOVER_ATTEMPTS, DEFAULT_FAILOVER_ATTEMPTS
                        ),
                    ): NumberSelector(NumberSelectorConfig(min=0, max=100, step=1)),
                    vol.Required(
                        CONF_FAILOVER_COOLDOWN,
                        default=self._working_options.get(
                            CONF_FAILOVER_COOLDOWN, DEFAULT_FAILOVER_COOLDOWN
                        ),
                    ): NumberSelector(NumberSelectorConfig(min=10, max=86400, step=10)),
                }
            ),
        )

    async def async_step_providers(self, user_input=None) -> ConfigFlowResult:
        self._ensure_state()
        if user_input is not None:
            self._editing_provider = str(user_input[CONF_PROVIDER])
            if user_input[CONF_PROVIDER_ACTION] == "credentials":
                return await self.async_step_provider_credentials()
            return await self.async_step_provider_settings()
        options = [
            SelectOptionDict(
                value=provider,
                label=(
                    f"{PROVIDER_DISPLAY_NAMES[provider]} · "
                    f"{len(self._providers[provider].get('credentials', []))} key(s)"
                ),
            )
            for provider in (PROVIDER_GOOGLE, PROVIDER_AZURE, PROVIDER_TAVILY)
        ]
        return self.async_show_form(
            step_id="providers",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PROVIDER): SelectSelector(
                        SelectSelectorConfig(options=options)
                    ),
                    vol.Required(
                        CONF_PROVIDER_ACTION, default="settings"
                    ): SelectSelector(
                        SelectSelectorConfig(options=["settings", "credentials"])
                    ),
                }
            ),
        )

    async def async_step_provider_settings(self, user_input=None) -> ConfigFlowResult:
        self._ensure_state()
        provider = self._editing_provider
        current = self._provider()
        allowed = set(PROVIDER_CAPABILITIES[provider])
        errors: dict[str, str] = {}
        if user_input is not None:
            capabilities = {
                str(item) for item in user_input[CONF_PROVIDER_CAPABILITIES]
            }
            if not capabilities.issubset(allowed):
                errors[CONF_PROVIDER_CAPABILITIES] = "invalid_capabilities"
            elif not capabilities:
                errors[CONF_PROVIDER_CAPABILITIES] = "invalid_capabilities"
            if not errors:
                units: dict[str, int] = {}
                if provider == PROVIDER_GOOGLE:
                    units["*"] = int(user_input[CONF_MONTHLY_TOKEN_LIMIT])
                elif provider == PROVIDER_AZURE:
                    units["tts"] = int(user_input[CONF_MONTHLY_TTS_CHARACTER_LIMIT])
                    units["stt"] = int(user_input[CONF_MONTHLY_STT_SECONDS_LIMIT])
                else:
                    units["search"] = int(user_input[CONF_MONTHLY_SEARCH_CREDIT_LIMIT])
                    self._working_options.update(
                        {
                            CONF_TAVILY_SEARCH_DEPTH: str(
                                user_input[CONF_TAVILY_SEARCH_DEPTH]
                            ),
                            CONF_TAVILY_MAX_RESULTS: int(
                                user_input[CONF_TAVILY_MAX_RESULTS]
                            ),
                        }
                    )
                current.update(
                    {
                        "enabled": bool(user_input[CONF_ENABLED]),
                        "capabilities": sorted(capabilities),
                        "rotation_strategy": str(user_input[CONF_ROTATION_STRATEGY]),
                        "max_attempts": int(user_input[CONF_FAILOVER_ATTEMPTS]),
                        "cooldown_seconds": int(user_input[CONF_FAILOVER_COOLDOWN]),
                        "limits": {
                            "daily_request_limit": int(
                                user_input[CONF_DAILY_REQUEST_LIMIT]
                            ),
                            "monthly_request_limit": int(
                                user_input[CONF_MONTHLY_REQUEST_LIMIT]
                            ),
                            "monthly_unit_limits": units,
                        },
                    }
                )
                return await self.async_step_providers()

        limits = current.get("limits", {})
        units = limits.get("monthly_unit_limits", {})
        schema: dict[Any, Any] = {
            vol.Required(CONF_ENABLED, default=current.get("enabled", True)): bool,
            vol.Required(
                CONF_PROVIDER_CAPABILITIES,
                default=current.get("capabilities", sorted(allowed)),
            ): SelectSelector(
                SelectSelectorConfig(options=sorted(allowed), multiple=True)
            ),
            vol.Required(
                CONF_ROTATION_STRATEGY,
                default=current.get("rotation_strategy", DEFAULT_ROTATION_STRATEGY),
            ): SelectSelector(SelectSelectorConfig(options=list(ROTATION_STRATEGIES))),
            vol.Required(
                CONF_FAILOVER_ATTEMPTS, default=current.get("max_attempts", 0)
            ): NumberSelector(NumberSelectorConfig(min=0, max=100, step=1)),
            vol.Required(
                CONF_FAILOVER_COOLDOWN,
                default=current.get("cooldown_seconds", DEFAULT_FAILOVER_COOLDOWN),
            ): NumberSelector(NumberSelectorConfig(min=10, max=86400, step=10)),
            vol.Optional(
                CONF_DAILY_REQUEST_LIMIT,
                default=limits.get("daily_request_limit", 0),
            ): NumberSelector(NumberSelectorConfig(min=0, max=1000000, step=1)),
            vol.Optional(
                CONF_MONTHLY_REQUEST_LIMIT,
                default=limits.get("monthly_request_limit", 0),
            ): NumberSelector(NumberSelectorConfig(min=0, max=10000000, step=1)),
        }
        if provider == PROVIDER_GOOGLE:
            schema[
                vol.Optional(CONF_MONTHLY_TOKEN_LIMIT, default=units.get("*", 0))
            ] = NumberSelector(NumberSelectorConfig(min=0, max=1000000000, step=1000))
        elif provider == PROVIDER_AZURE:
            schema[
                vol.Optional(
                    CONF_MONTHLY_TTS_CHARACTER_LIMIT,
                    default=units.get("tts", 0),
                )
            ] = NumberSelector(NumberSelectorConfig(min=0, max=1000000000, step=1000))
            schema[
                vol.Optional(
                    CONF_MONTHLY_STT_SECONDS_LIMIT,
                    default=units.get("stt", 0),
                )
            ] = NumberSelector(NumberSelectorConfig(min=0, max=100000000, step=60))
        else:
            schema[
                vol.Optional(
                    CONF_MONTHLY_SEARCH_CREDIT_LIMIT,
                    default=units.get("search", 0),
                )
            ] = NumberSelector(NumberSelectorConfig(min=0, max=10000000, step=1))
            schema[
                vol.Required(
                    CONF_TAVILY_SEARCH_DEPTH,
                    default=self._working_options.get(
                        CONF_TAVILY_SEARCH_DEPTH, DEFAULT_TAVILY_SEARCH_DEPTH
                    ),
                )
            ] = SelectSelector(SelectSelectorConfig(options=["basic", "advanced"]))
            schema[
                vol.Required(
                    CONF_TAVILY_MAX_RESULTS,
                    default=self._working_options.get(
                        CONF_TAVILY_MAX_RESULTS, DEFAULT_TAVILY_MAX_RESULTS
                    ),
                )
            ] = NumberSelector(NumberSelectorConfig(min=1, max=10, step=1))
        return self.async_show_form(
            step_id="provider_settings",
            data_schema=vol.Schema(schema),
            errors=errors,
            description_placeholders={
                "provider_name": PROVIDER_DISPLAY_NAMES[provider]
            },
        )

    async def async_step_provider_credentials(
        self, user_input=None
    ) -> ConfigFlowResult:
        self._ensure_state()
        credentials = self._provider().setdefault("credentials", [])
        options = [SelectOptionDict(value="__add__", label="+ API key")]
        options.extend(
            SelectOptionDict(
                value=item["id"],
                label=(
                    f"{item.get('name', item['id'])} · "
                    f"{'ON' if item.get('enabled', True) else 'OFF'}"
                ),
            )
            for item in credentials
        )
        if user_input is not None:
            action = str(user_input[CONF_CREDENTIAL_ACTION])
            if action == "back":
                return await self.async_step_providers()
            selected = str(user_input[CONF_CREDENTIAL_ID])
            if selected == "__add__":
                return await self.async_step_add_credential()
            self._editing_id = selected
            if action == "delete":
                return await self.async_step_delete_credential()
            return await self.async_step_edit_credential()
        return self.async_show_form(
            step_id="provider_credentials",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CREDENTIAL_ID): SelectSelector(
                        SelectSelectorConfig(options=options)
                    ),
                    vol.Required(
                        CONF_CREDENTIAL_ACTION, default="edit"
                    ): SelectSelector(
                        SelectSelectorConfig(options=["edit", "delete", "back"])
                    ),
                }
            ),
            description_placeholders={
                "provider_name": PROVIDER_DISPLAY_NAMES[self._editing_provider],
                "credential_count": str(len(credentials)),
            },
        )

    async def async_step_add_credential(self, user_input=None) -> ConfigFlowResult:
        return await self._async_credential_form(user_input)

    async def async_step_edit_credential(self, user_input=None) -> ConfigFlowResult:
        current = next(
            item
            for item in self._provider().setdefault("credentials", [])
            if item["id"] == self._editing_id
        )
        return await self._async_credential_form(user_input, current=current)

    async def async_step_delete_credential(self, user_input=None) -> ConfigFlowResult:
        credentials = self._provider().setdefault("credentials", [])
        current = next(item for item in credentials if item["id"] == self._editing_id)
        if user_input is not None and user_input.get("confirm") is True:
            self._provider()["credentials"] = [
                item for item in credentials if item["id"] != self._editing_id
            ]
            self._editing_id = None
            return await self.async_step_provider_credentials()
        return self.async_show_form(
            step_id="delete_credential",
            data_schema=vol.Schema({vol.Required("confirm", default=False): bool}),
            description_placeholders={"credential_name": current.get("name", "")},
        )

    async def _async_credential_form(
        self, user_input: dict[str, Any] | None, *, current=None
    ) -> ConfigFlowResult:
        credentials = self._provider().setdefault("credentials", [])
        current = current or {}
        errors: dict[str, str] = {}
        if user_input is not None:
            secret = str(user_input.get(CONF_API_KEY, "")).strip() or str(
                current.get("api_key", "")
            )
            region = (
                str(user_input.get(CONF_AZURE_REGION, "")).strip().lower()
                if self._editing_provider == PROVIDER_AZURE
                else ""
            )
            if not secret:
                errors[CONF_API_KEY] = "key_required"
            elif any(
                item.get("id") != current.get("id")
                and str(item.get("api_key", "")).strip() == secret
                and str(item.get("region", "")).strip().lower() == region
                for item in credentials
            ):
                errors["base"] = "duplicate_credential"
            if not errors:
                saved = {
                    "id": current.get("id", uuid4().hex),
                    "name": str(user_input[CONF_CREDENTIAL_NAME]).strip(),
                    "api_key": secret,
                    "enabled": bool(user_input[CONF_ENABLED]),
                    "priority": int(current.get("priority", len(credentials) + 1)),
                }
                if self._editing_provider == PROVIDER_AZURE:
                    saved["region"] = region
                if current:
                    self._provider()["credentials"] = [
                        saved if item["id"] == current["id"] else item
                        for item in credentials
                    ]
                else:
                    credentials.append(saved)
                return await self.async_step_provider_credentials()

        schema: dict[Any, Any] = {
            vol.Required(
                CONF_CREDENTIAL_NAME,
                default=current.get(
                    "name", f"{PROVIDER_DISPLAY_NAMES[self._editing_provider]} key"
                ),
            ): str,
            vol.Optional(CONF_API_KEY): TextSelector(
                TextSelectorConfig(type=TextSelectorType.PASSWORD)
            ),
            vol.Required(CONF_ENABLED, default=current.get("enabled", True)): bool,
        }
        if self._editing_provider == PROVIDER_AZURE:
            schema[
                vol.Required(
                    CONF_AZURE_REGION,
                    default=current.get("region", DEFAULT_AZURE_REGION),
                )
            ] = str
        return self.async_show_form(
            step_id="edit_credential" if current else "add_credential",
            data_schema=vol.Schema(schema),
            errors=errors,
            description_placeholders={
                "provider_name": PROVIDER_DISPLAY_NAMES[self._editing_provider]
            },
        )

    async def async_step_routes(self, user_input=None) -> ConfigFlowResult:
        self._ensure_state()
        fields = {
            "route_ai_task": "ai_task",
            "route_conversation": "conversation",
            "route_stt": "stt",
            "route_tts": "tts",
            "route_search": "search",
            "route_image": "image",
        }
        errors: dict[str, str] = {}
        if user_input is not None:
            parsed = {
                capability: self._normalize_route(user_input.get(field, []))
                for field, capability in fields.items()
            }
            for field, capability in fields.items():
                route = parsed[capability]
                if not route and not (
                    capability == "search"
                    and not self._working_options.get(
                        CONF_SEARCH_ENABLED, DEFAULT_SEARCH_ENABLED
                    )
                ):
                    errors[field] = "route_required"
                    continue
                if any(
                    provider not in PROVIDER_CAPABILITIES
                    or capability not in PROVIDER_CAPABILITIES[provider]
                    for provider in route
                ):
                    errors[field] = "invalid_route"
                    continue
                eligible = {
                    option["value"]
                    for option in self._route_options(capability)
                }
                if any(provider not in eligible for provider in route):
                    errors[field] = "invalid_route"
            if not errors:
                self._routes.update(parsed)
                return await self.async_step_init()
        return self.async_show_form(
            step_id="routes",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        field, default=self._routes.get(capability, [])
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=self._route_options(
                                capability, self._routes.get(capability, [])
                            ),
                            multiple=True,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    )
                    for field, capability in fields.items()
                }
            ),
            errors=errors,
        )

    async def async_step_latency_feedback(self, user_input=None) -> ConfigFlowResult:
        self._ensure_state()
        if user_input is not None:
            phrases = []
            for value in str(user_input[CONF_LATENCY_PHRASES]).splitlines():
                phrase = value.strip()
                if phrase and phrase not in phrases:
                    phrases.append(phrase)
            self._working_options.update(
                {
                    CONF_LATENCY_FEEDBACK_ENABLED: bool(
                        user_input[CONF_LATENCY_FEEDBACK_ENABLED]
                    ),
                    CONF_LATENCY_FEEDBACK_DELAY_MS: int(
                        user_input[CONF_LATENCY_FEEDBACK_DELAY_MS]
                    ),
                    CONF_LATENCY_PHRASES: phrases or list(DEFAULT_LATENCY_PHRASES),
                }
            )
            return await self.async_step_init()
        configured_phrases = self._working_options.get(
            CONF_LATENCY_PHRASES, DEFAULT_LATENCY_PHRASES
        )
        if not isinstance(configured_phrases, str):
            configured_phrases = "\n".join(configured_phrases)
        return self.async_show_form(
            step_id="latency_feedback",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_LATENCY_FEEDBACK_ENABLED,
                        default=self._working_options.get(
                            CONF_LATENCY_FEEDBACK_ENABLED, True
                        ),
                    ): bool,
                    vol.Required(
                        CONF_LATENCY_FEEDBACK_DELAY_MS,
                        default=self._working_options.get(
                            CONF_LATENCY_FEEDBACK_DELAY_MS,
                            DEFAULT_LATENCY_FEEDBACK_DELAY_MS,
                        ),
                    ): NumberSelector(NumberSelectorConfig(min=0, max=10000, step=100)),
                    vol.Required(
                        CONF_LATENCY_PHRASES, default=configured_phrases
                    ): TextSelector(TextSelectorConfig(multiline=True)),
                }
            ),
        )

    async def async_step_generate_latency_audio(
        self, user_input=None
    ) -> ConfigFlowResult:
        """Generate/update button for the currently saved phrase list."""
        if user_input is not None:
            return await self.async_step_init()
        result = await self.config_entry.runtime_data.feedback.async_generate()
        return self.async_show_form(
            step_id="generate_latency_audio",
            data_schema=vol.Schema({}),
            description_placeholders={
                "generated": str(result["generated"]),
                "skipped": str(result["skipped"]),
                "failed": str(result["failed"]),
            },
        )

    async def async_step_preview_latency_audio(
        self, user_input=None
    ) -> ConfigFlowResult:
        """Preview one generated phrase from the options UI."""
        feedback = self.config_entry.runtime_data.feedback
        if user_input is not None:
            await feedback.async_play_phrase(
                str(user_input[CONF_LATENCY_PHRASES]),
                str(user_input[CONF_OUTPUT_MEDIA_PLAYER]),
            )
            return await self.async_step_init()
        return self.async_show_form(
            step_id="preview_latency_audio",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_LATENCY_PHRASES): SelectSelector(
                        SelectSelectorConfig(options=list(feedback.phrases))
                    ),
                    vol.Required(CONF_OUTPUT_MEDIA_PLAYER): EntitySelector(
                        EntitySelectorConfig(domain="media_player")
                    ),
                }
            ),
        )

    async def async_step_save(self, user_input=None) -> ConfigFlowResult:
        self._ensure_state()
        google = self._providers[PROVIDER_GOOGLE]
        has_google = google.get("enabled", True) and any(
            credential.get("enabled", True)
            and str(credential.get("api_key", "")).strip()
            for credential in google.get("credentials", [])
        )
        if not has_google:
            return await self.async_step_google_required()
        self._working_options[CONF_PROVIDERS] = self._providers
        self._working_options[CONF_ROUTES] = self._routes
        for legacy in (CONF_PROVIDER_INSTANCES, CONF_CREDENTIALS, CONF_PROVIDER_LIMITS):
            self._working_options.pop(legacy, None)
        return self.async_create_entry(title="", data=self._working_options)

    async def async_step_google_required(self, user_input=None) -> ConfigFlowResult:
        if user_input is not None:
            return await self.async_step_init()
        return self.async_show_form(
            step_id="google_required", data_schema=vol.Schema({})
        )


class LLMSubentryFlowHandler(ConfigSubentryFlow):
    """Flow for managing conversation subentries."""

    last_rendered_recommended = False
    last_rendered_route: tuple[str, ...] = ()
    last_rendered_image_route: tuple[str, ...] = ()

    @property
    def _genai_client(self) -> genai.Client:
        """Return the Google Generative AI client."""
        return self._get_entry().runtime_data.providers.google_client

    @property
    def _provider_hub(self):
        """Return the Luna Provider Hub."""
        return self._get_entry().runtime_data.providers

    @property
    def _is_new(self) -> bool:
        """Return if this is a new subentry."""
        return self.source == "user"

    @property
    def _capability(self) -> ProviderCapability:
        """Return the primary capability configured by this subentry."""
        return {
            "conversation": ProviderCapability.CONVERSATION,
            "stt": ProviderCapability.STT,
            "tts": ProviderCapability.TTS,
            "ai_task_data": ProviderCapability.AI_TASK,
        }[self._subentry_type]

    @staticmethod
    def _normalize_route(value: Any) -> list[str]:
        """Normalize a searchable multi-select route without changing order."""
        values = value if isinstance(value, (list, tuple)) else [value]
        route: list[str] = []
        for item in values:
            provider = str(item).strip().lower()
            if provider and provider not in route:
                route.append(provider)
        return route

    def _save_parent_routes(
        self, route: list[str], image_route: list[str] | None = None
    ) -> None:
        """Persist the service route in the single central route catalogue."""
        entry = self._get_entry()
        routes = routes_from_entry(entry)
        routes[self._capability.value] = route
        if image_route is not None:
            routes[ProviderCapability.IMAGE.value] = image_route
        parent_options = dict(entry.options)
        parent_options[CONF_ROUTES] = routes
        self.hass.config_entries.async_update_entry(entry, options=parent_options)

    def _validate_route(
        self, route: list[str], capability: ProviderCapability
    ) -> bool:
        """Validate every selected provider against enabled credentials."""
        if not route:
            return False
        try:
            for provider in route:
                self._provider_hub.validate_capability(provider, capability)
        except ProviderError:
            return False
        return True

    async def async_step_set_options(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Set conversation options."""
        # abort if entry is not loaded
        if self._get_entry().state is not ConfigEntryState.LOADED:
            return self.async_abort(reason="entry_not_loaded")

        errors: dict[str, str] = {}

        if user_input is None:
            if self._is_new:
                options: dict[str, Any]
                if self._subentry_type == "tts":
                    options = RECOMMENDED_TTS_OPTIONS.copy()
                elif self._subentry_type == "ai_task_data":
                    options = RECOMMENDED_AI_TASK_OPTIONS.copy()
                elif self._subentry_type == "stt":
                    options = RECOMMENDED_STT_OPTIONS.copy()
                else:
                    options = RECOMMENDED_CONVERSATION_OPTIONS.copy()
            else:
                # If this is a reconfiguration, we need to copy the existing options
                # so that we can show the current values in the form.
                options = self._get_reconfigure_subentry().data.copy()

            self.last_rendered_recommended = cast(
                bool, options.get(CONF_RECOMMENDED, False)
            )
            central_routes = routes_from_entry(self._get_entry())
            self.last_rendered_route = tuple(
                central_routes.get(self._capability.value, [])
            )
            self.last_rendered_image_route = tuple(
                central_routes.get(ProviderCapability.IMAGE.value, [])
            )

        else:
            selected_route = self._normalize_route(
                user_input.get(CONF_SERVICE_ROUTE, [])
            )
            selected_image_route = self._normalize_route(
                user_input.get(CONF_IMAGE_ROUTE, [])
            )
            route_is_valid = self._validate_route(selected_route, self._capability)
            if not route_is_valid:
                errors[CONF_SERVICE_ROUTE] = "invalid_service_route"
            if self._subentry_type == "ai_task_data" and not self._validate_route(
                selected_image_route, ProviderCapability.IMAGE
            ):
                errors[CONF_IMAGE_ROUTE] = "invalid_service_route"

            rendered_routes_match = (
                tuple(selected_route) == self.last_rendered_route
                and (
                    self._subentry_type != "ai_task_data"
                    or tuple(selected_image_route) == self.last_rendered_image_route
                )
            )
            if (
                user_input[CONF_RECOMMENDED] == self.last_rendered_recommended
                and rendered_routes_match
                and not errors
            ):
                if not user_input.get(CONF_LLM_HASS_API):
                    user_input.pop(CONF_LLM_HASS_API, None)

                if (
                    self._subentry_type == "conversation"
                    and user_input.get(CONF_AUDIO_OUTPUT, DEFAULT_AUDIO_OUTPUT)
                    != AUDIO_OUTPUT_ATOM
                    and not user_input.get(CONF_OUTPUT_MEDIA_PLAYER)
                ):
                    errors[CONF_OUTPUT_MEDIA_PLAYER] = "media_player_required"

                if not errors:
                    saved_data = dict(user_input)
                    saved_data.pop(CONF_SERVICE_ROUTE, None)
                    saved_data.pop(CONF_IMAGE_ROUTE, None)
                    if self._is_new:
                        result = self.async_create_entry(
                            title=saved_data.pop(CONF_NAME),
                            data=saved_data,
                        )
                    else:
                        result = self.async_update_and_abort(
                            self._get_entry(),
                            self._get_reconfigure_subentry(),
                            data=saved_data,
                        )
                    self._save_parent_routes(
                        selected_route,
                        selected_image_route
                        if self._subentry_type == "ai_task_data"
                        else None,
                    )
                    return result

            # Re-render the options again, now with the recommended options shown/hidden
            self.last_rendered_recommended = user_input[CONF_RECOMMENDED]
            if route_is_valid:
                self.last_rendered_route = tuple(selected_route)
            if self._subentry_type == "ai_task_data" and not errors.get(
                CONF_IMAGE_ROUTE
            ):
                self.last_rendered_image_route = tuple(selected_image_route)

            options = user_input

        schema = await google_generative_ai_config_option_schema(
            self.hass,
            self._is_new,
            self._subentry_type,
            options,
            self._genai_client,
            self._get_entry(),
        )
        return self.async_show_form(
            step_id="set_options", data_schema=vol.Schema(schema), errors=errors
        )

    async_step_reconfigure = async_step_set_options
    async_step_user = async_step_set_options


async def google_generative_ai_config_option_schema(
    hass: HomeAssistant,
    is_new: bool,
    subentry_type: str,
    options: Mapping[str, Any],
    genai_client: genai.Client,
    config_entry: ConfigEntry,
) -> dict:
    """Return a schema for Google Generative AI completion options."""
    hass_apis: list[SelectOptionDict] = [
        SelectOptionDict(
            label=api.name,
            value=api.id,
        )
        for api in llm.async_get_apis(hass)
    ]
    if suggested_llm_apis := options.get(CONF_LLM_HASS_API):
        if isinstance(suggested_llm_apis, str):
            suggested_llm_apis = [suggested_llm_apis]
        known_apis = {api.id for api in llm.async_get_apis(hass)}
        suggested_llm_apis = [api for api in suggested_llm_apis if api in known_apis]

    if is_new:
        if CONF_NAME in options:
            default_name = options[CONF_NAME]
        elif subentry_type == "tts":
            default_name = DEFAULT_TTS_NAME
        elif subentry_type == "ai_task_data":
            default_name = DEFAULT_AI_TASK_NAME
        elif subentry_type == "stt":
            default_name = DEFAULT_STT_NAME
        else:
            default_name = DEFAULT_CONVERSATION_NAME
        schema: dict[vol.Required | vol.Optional, Any] = {
            # Name field is no longer allowed in config flow schemas
            # pylint: disable-next=home-assistant-config-flow-name-field
            vol.Required(CONF_NAME, default=default_name): str,
        }
    else:
        schema = {}

    capability = {
        "conversation": ProviderCapability.CONVERSATION,
        "stt": ProviderCapability.STT,
        "tts": ProviderCapability.TTS,
        "ai_task_data": ProviderCapability.AI_TASK,
    }[subentry_type]
    central_routes = routes_from_entry(config_entry)
    route = LLMSubentryFlowHandler._normalize_route(
        options.get(
            CONF_SERVICE_ROUTE,
            central_routes.get(capability.value, []),
        )
    )
    image_route = LLMSubentryFlowHandler._normalize_route(
        options.get(
            CONF_IMAGE_ROUTE,
            central_routes.get(ProviderCapability.IMAGE.value, []),
        )
    )

    def route_options(
        route_capability: ProviderCapability, current: list[str]
    ) -> list[SelectOptionDict]:
        """Build a searchable provider selector for one service."""
        configured_providers = providers_from_entry(config_entry)
        selector_options: list[SelectOptionDict] = []
        for provider, supported in PROVIDER_CAPABILITIES.items():
            provider_config = configured_providers.get(provider, {})
            enabled = bool(provider_config.get("enabled", True))
            configured = route_capability.value in provider_config.get(
                "capabilities", supported
            )
            if enabled and configured and route_capability.value in supported:
                selector_options.append(
                    SelectOptionDict(
                        value=provider, label=PROVIDER_DISPLAY_NAMES[provider]
                    )
                )
            elif provider in current:
                selector_options.append(
                    SelectOptionDict(
                        value=provider,
                        label=f"{PROVIDER_DISPLAY_NAMES[provider]} ⚠",
                    )
                )
        return selector_options

    schema.update(
        {
            vol.Required(CONF_SERVICE_ROUTE, default=route): SelectSelector(
                SelectSelectorConfig(
                    options=route_options(capability, route),
                    multiple=True,
                    mode=SelectSelectorMode.DROPDOWN,
                )
            )
        }
    )
    if subentry_type == "ai_task_data":
        schema.update(
            {
                vol.Required(CONF_IMAGE_ROUTE, default=image_route): SelectSelector(
                    SelectSelectorConfig(
                        options=route_options(
                            ProviderCapability.IMAGE, image_route
                        ),
                        multiple=True,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                )
            }
        )

    has_google = PROVIDER_GOOGLE in route
    has_azure = PROVIDER_AZURE in route

    if subentry_type == "conversation":
        schema.update(
            {
                vol.Optional(
                    CONF_PROMPT,
                    description={
                        "suggested_value": options.get(
                            CONF_PROMPT, llm.DEFAULT_INSTRUCTIONS_PROMPT
                        )
                    },
                ): TemplateSelector(),
                vol.Optional(
                    CONF_LLM_HASS_API,
                    description={"suggested_value": suggested_llm_apis},
                ): SelectSelector(
                    SelectSelectorConfig(options=hass_apis, multiple=True)
                ),
                vol.Optional(
                    CONF_PERSONALITY,
                    default=options.get(CONF_PERSONALITY, DEFAULT_PERSONALITY),
                ): SelectSelector(
                    SelectSelectorConfig(
                        mode=SelectSelectorMode.DROPDOWN,
                        options=[
                            "playful",
                            "warm",
                            "direct",
                            "teacher",
                            "technical",
                        ],
                        translation_key=CONF_PERSONALITY,
                    )
                ),
                vol.Optional(
                    CONF_RESPONSE_LENGTH,
                    default=options.get(CONF_RESPONSE_LENGTH, DEFAULT_RESPONSE_LENGTH),
                ): SelectSelector(
                    SelectSelectorConfig(
                        mode=SelectSelectorMode.DROPDOWN,
                        options=["very_short", "short", "balanced", "detailed"],
                        translation_key=CONF_RESPONSE_LENGTH,
                    )
                ),
                vol.Optional(
                    CONF_LATENCY_PROFILE,
                    default=options.get(CONF_LATENCY_PROFILE, DEFAULT_LATENCY_PROFILE),
                ): SelectSelector(
                    SelectSelectorConfig(
                        mode=SelectSelectorMode.DROPDOWN,
                        options=["fast", "balanced", "quality"],
                        translation_key=CONF_LATENCY_PROFILE,
                    )
                ),
                vol.Optional(
                    CONF_AUDIO_OUTPUT,
                    default=options.get(CONF_AUDIO_OUTPUT, DEFAULT_AUDIO_OUTPUT),
                ): SelectSelector(
                    SelectSelectorConfig(
                        mode=SelectSelectorMode.DROPDOWN,
                        options=[
                            AUDIO_OUTPUT_ATOM,
                            AUDIO_OUTPUT_GOOGLE_NEST,
                            AUDIO_OUTPUT_MEDIA_PLAYER,
                        ],
                        translation_key=CONF_AUDIO_OUTPUT,
                    )
                ),
                vol.Optional(
                    CONF_OUTPUT_MEDIA_PLAYER,
                    description={
                        "suggested_value": options.get(CONF_OUTPUT_MEDIA_PLAYER)
                    },
                ): EntitySelector(EntitySelectorConfig(domain="media_player")),
                vol.Optional(
                    CONF_OUTPUT_TTS_ENTITY,
                    description={
                        "suggested_value": options.get(CONF_OUTPUT_TTS_ENTITY)
                    },
                ): EntitySelector(EntitySelectorConfig(domain="tts")),
            }
        )
    elif subentry_type == "stt":
        schema.update(
            {
                vol.Optional(
                    CONF_PROMPT,
                    description={
                        "suggested_value": options.get(CONF_PROMPT, DEFAULT_STT_PROMPT)
                    },
                ): TemplateSelector(),
            }
        )
        if has_azure:
            schema.update(
                {
                    vol.Optional(
                        CONF_AZURE_STT_PROFANITY,
                        default=options.get(
                            CONF_AZURE_STT_PROFANITY,
                            DEFAULT_AZURE_STT_PROFANITY,
                        ),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=["raw", "masked", "removed"],
                            translation_key=CONF_AZURE_STT_PROFANITY,
                        )
                    )
                }
            )
    elif subentry_type == "tts":
        schema.update(
            {
                vol.Optional(
                    CONF_PROMPT,
                    description={
                        "suggested_value": options.get(
                            CONF_PROMPT, DEFAULT_TTS_STYLE_PROMPT
                        )
                    },
                ): TemplateSelector(),
                vol.Optional(
                    CONF_VOICE_MOOD,
                    default=options.get(CONF_VOICE_MOOD, DEFAULT_VOICE_MOOD),
                ): SelectSelector(
                    SelectSelectorConfig(
                        mode=SelectSelectorMode.DROPDOWN,
                        options=[
                            "cheerful",
                            "warm",
                            "calm",
                            "enthusiastic",
                            "professional",
                        ],
                        translation_key=CONF_VOICE_MOOD,
                    )
                ),
                vol.Optional(
                    CONF_SPEAKING_PACE,
                    default=options.get(CONF_SPEAKING_PACE, DEFAULT_SPEAKING_PACE),
                ): SelectSelector(
                    SelectSelectorConfig(
                        mode=SelectSelectorMode.DROPDOWN,
                        options=["slow", "natural", "fast"],
                        translation_key=CONF_SPEAKING_PACE,
                    )
                ),
            }
        )
        if has_azure:
            schema.update(
                {
                    vol.Required(
                        CONF_AZURE_VOICE,
                        default=options.get(CONF_AZURE_VOICE, DEFAULT_AZURE_VOICE),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            mode=SelectSelectorMode.DROPDOWN,
                            options=list(AZURE_PT_BR_VOICES),
                        )
                    ),
                    vol.Optional(
                        CONF_AZURE_OUTPUT_FORMAT,
                        default=options.get(
                            CONF_AZURE_OUTPUT_FORMAT, DEFAULT_AZURE_OUTPUT_FORMAT
                        ),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            mode=SelectSelectorMode.DROPDOWN,
                            options=[
                                "riff-16khz-16bit-mono-pcm",
                                DEFAULT_AZURE_OUTPUT_FORMAT,
                                "riff-48khz-16bit-mono-pcm",
                            ],
                        )
                    ),
                }
            )
        if has_google:
            schema.update(
                {
                    vol.Required(
                        CONF_GOOGLE_TTS_VOICE,
                        default=options.get(
                            CONF_GOOGLE_TTS_VOICE, DEFAULT_GOOGLE_TTS_VOICE
                        ),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            mode=SelectSelectorMode.DROPDOWN,
                            options=list(GOOGLE_TTS_VOICES),
                        )
                    )
                }
            )

    schema.update(
        {
            vol.Required(
                CONF_RECOMMENDED, default=options.get(CONF_RECOMMENDED, False)
            ): bool,
        }
    )

    if options.get(CONF_RECOMMENDED):
        return schema

    has_google_image = (
        subentry_type == "ai_task_data" and PROVIDER_GOOGLE in image_route
    )
    if not has_google and not has_google_image:
        return schema

    api_models_pager = await genai_client.aio.models.list(config={"query_base": True})
    api_models = [api_model async for api_model in api_models_pager]
    models = [
        SelectOptionDict(
            label=api_model.name.lstrip("models/"),
            value=api_model.name,
        )
        for api_model in sorted(
            api_models, key=lambda x: (x.name or "").lstrip("models/")
        )
        if (
            api_model.name
            and ("tts" in api_model.name) == (subentry_type == "tts")
            and (
                subentry_type == "tts"
                or "image" not in api_model.name.casefold()
            )
            and "vision" not in api_model.name
            and api_model.supported_actions
            and "generateContent" in api_model.supported_actions
        )
    ]

    harm_block_thresholds: list[SelectOptionDict] = [
        SelectOptionDict(
            label="Block none",
            value="BLOCK_NONE",
        ),
        SelectOptionDict(
            label="Block few",
            value="BLOCK_ONLY_HIGH",
        ),
        SelectOptionDict(
            label="Block some",
            value="BLOCK_MEDIUM_AND_ABOVE",
        ),
        SelectOptionDict(
            label="Block most",
            value="BLOCK_LOW_AND_ABOVE",
        ),
    ]
    harm_block_thresholds_selector = SelectSelector(
        SelectSelectorConfig(
            mode=SelectSelectorMode.DROPDOWN, options=harm_block_thresholds
        )
    )

    if subentry_type == "tts":
        default_model = RECOMMENDED_TTS_MODEL
    elif subentry_type == "stt":
        default_model = RECOMMENDED_STT_MODEL
    else:
        default_model = RECOMMENDED_CHAT_MODEL

    if has_google:
        schema.update(
            {
                vol.Optional(
                    CONF_CHAT_MODEL,
                    description={"suggested_value": options.get(CONF_CHAT_MODEL)},
                    default=default_model,
                ): SelectSelector(
                    SelectSelectorConfig(
                        mode=SelectSelectorMode.DROPDOWN, options=models
                    )
                ),
                vol.Optional(
                    CONF_TEMPERATURE,
                    description={"suggested_value": options.get(CONF_TEMPERATURE)},
                    default=RECOMMENDED_TEMPERATURE,
                ): NumberSelector(NumberSelectorConfig(min=0, max=2, step=0.05)),
            }
        )

    if has_google_image:
        image_models = [
            SelectOptionDict(
                label=api_model.name.lstrip("models/"),
                value=api_model.name,
            )
            for api_model in sorted(
                api_models, key=lambda x: (x.name or "").lstrip("models/")
            )
            if (
                api_model.name
                and "image" in api_model.name.casefold()
                and api_model.supported_actions
                and "generateContent" in api_model.supported_actions
            )
        ]
        if not any(item["value"] == RECOMMENDED_IMAGE_MODEL for item in image_models):
            image_models.insert(
                0,
                SelectOptionDict(
                    label=RECOMMENDED_IMAGE_MODEL.lstrip("models/"),
                    value=RECOMMENDED_IMAGE_MODEL,
                ),
            )
        schema.update(
            {
                vol.Optional(
                    CONF_IMAGE_MODEL,
                    description={
                        "suggested_value": options.get(CONF_IMAGE_MODEL)
                    },
                    default=RECOMMENDED_IMAGE_MODEL,
                ): SelectSelector(
                    SelectSelectorConfig(
                        mode=SelectSelectorMode.DROPDOWN,
                        options=image_models,
                    )
                )
            }
        )

    if has_google and subentry_type != "tts":
        schema.update(
            {
                vol.Optional(
                    CONF_TOP_P,
                    description={"suggested_value": options.get(CONF_TOP_P)},
                    default=RECOMMENDED_TOP_P,
                ): NumberSelector(NumberSelectorConfig(min=0, max=1, step=0.05)),
                vol.Optional(
                    CONF_TOP_K,
                    description={"suggested_value": options.get(CONF_TOP_K)},
                    default=RECOMMENDED_TOP_K,
                ): int,
                vol.Optional(
                    CONF_MAX_TOKENS,
                    description={"suggested_value": options.get(CONF_MAX_TOKENS)},
                    default=RECOMMENDED_MAX_TOKENS,
                ): int,
                vol.Optional(
                    CONF_THINKING_BUDGET,
                    description={"suggested_value": options.get(CONF_THINKING_BUDGET)},
                    default=RECOMMENDED_THINKING_BUDGET,
                ): vol.All(
                    NumberSelector(
                        NumberSelectorConfig(
                            min=-1, max=24576, step=1, mode=NumberSelectorMode.BOX
                        )
                    ),
                    vol.Coerce(int),
                ),
                vol.Optional(
                    CONF_THINKING_LEVEL,
                    description={"suggested_value": options.get(CONF_THINKING_LEVEL)},
                    default=RECOMMENDED_THINKING_LEVEL,
                ): SelectSelector(
                    SelectSelectorConfig(
                        mode=SelectSelectorMode.DROPDOWN,
                        translation_key=CONF_THINKING_LEVEL,
                        options=[
                            "auto",
                            "minimal",
                            "low",
                            "medium",
                            "high",
                        ],
                    )
                ),
                vol.Optional(
                    CONF_HARASSMENT_BLOCK_THRESHOLD,
                    description={
                        "suggested_value": options.get(CONF_HARASSMENT_BLOCK_THRESHOLD)
                    },
                    default=RECOMMENDED_HARM_BLOCK_THRESHOLD,
                ): harm_block_thresholds_selector,
                vol.Optional(
                    CONF_HATE_BLOCK_THRESHOLD,
                    description={
                        "suggested_value": options.get(CONF_HATE_BLOCK_THRESHOLD)
                    },
                    default=RECOMMENDED_HARM_BLOCK_THRESHOLD,
                ): harm_block_thresholds_selector,
                vol.Optional(
                    CONF_SEXUAL_BLOCK_THRESHOLD,
                    description={
                        "suggested_value": options.get(CONF_SEXUAL_BLOCK_THRESHOLD)
                    },
                    default=RECOMMENDED_HARM_BLOCK_THRESHOLD,
                ): harm_block_thresholds_selector,
                vol.Optional(
                    CONF_DANGEROUS_BLOCK_THRESHOLD,
                    description={
                        "suggested_value": options.get(CONF_DANGEROUS_BLOCK_THRESHOLD)
                    },
                    default=RECOMMENDED_HARM_BLOCK_THRESHOLD,
                ): harm_block_thresholds_selector,
            }
        )
    return schema
