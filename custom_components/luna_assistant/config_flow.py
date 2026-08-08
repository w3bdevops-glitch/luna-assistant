# Modified for Luna Assistant.
# Derived from Home Assistant Core's Google Gemini integration,
# licensed under the Apache License 2.0.

"""Config flow for Luna Assistant integration."""

import logging
from collections.abc import Mapping
from functools import partial
from typing import Any, cast, override
from uuid import uuid4

import voluptuous as vol
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
    CONF_LATENCY_PROFILE,
    CONF_MAX_TOKENS,
    CONF_MONTHLY_REQUEST_LIMIT,
    CONF_MONTHLY_STT_SECONDS_LIMIT,
    CONF_MONTHLY_TOKEN_LIMIT,
    CONF_MONTHLY_TTS_CHARACTER_LIMIT,
    CONF_OUTPUT_MEDIA_PLAYER,
    CONF_OUTPUT_TTS_ENTITY,
    CONF_PERSONALITY,
    CONF_PRIORITY,
    CONF_PROVIDER,
    CONF_PROVIDER_LIMITS,
    CONF_RECOMMENDED,
    CONF_RESPONSE_LENGTH,
    CONF_ROTATION_STRATEGY,
    CONF_SEXUAL_BLOCK_THRESHOLD,
    CONF_SPEAKING_PACE,
    CONF_TEMPERATURE,
    CONF_THINKING_BUDGET,
    CONF_THINKING_LEVEL,
    CONF_TOP_K,
    CONF_TOP_P,
    CONF_USE_GOOGLE_SEARCH_TOOL,
    CONF_VOICE_MOOD,
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
    DEFAULT_PROVIDER,
    DEFAULT_RESPONSE_LENGTH,
    DEFAULT_ROTATION_STRATEGY,
    DEFAULT_SPEAKING_PACE,
    DEFAULT_STT_NAME,
    DEFAULT_STT_PROMPT,
    DEFAULT_TITLE,
    DEFAULT_TTS_NAME,
    DEFAULT_TTS_STYLE_PROMPT,
    DEFAULT_VOICE_MOOD,
    DOMAIN,
    PROVIDER_AZURE,
    PROVIDER_GOOGLE,
    RECOMMENDED_AI_TASK_OPTIONS,
    RECOMMENDED_CHAT_MODEL,
    RECOMMENDED_CONVERSATION_OPTIONS,
    RECOMMENDED_HARM_BLOCK_THRESHOLD,
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
    RECOMMENDED_USE_GOOGLE_SEARCH_TOOL,
    ROTATION_STRATEGIES,
    TIMEOUT_MILLIS,
)
from .provider_hub import ProviderCapability, ProviderError
from .provider_hub.credentials import credentials_from_entry

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
    MINOR_VERSION = 8

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


class LunaAssistantOptionsFlow(OptionsFlow):
    """Manage provider credentials, budgets, rotation and failover."""

    def _ensure_state(self) -> None:
        if hasattr(self, "_working_options"):
            return
        self._working_options = dict(self.config_entry.options)
        self._credentials = credentials_from_entry(self.config_entry)
        self._editing_id: str | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        self._ensure_state()
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "general",
                "add_google",
                "add_azure",
                "manage_credentials",
                "save",
            ],
        )

    async def async_step_general(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        self._ensure_state()
        provider_limits = self._working_options.get(CONF_PROVIDER_LIMITS, {})
        google_limits = provider_limits.get(PROVIDER_GOOGLE, {})
        azure_limits = provider_limits.get(PROVIDER_AZURE, {})
        google_units = google_limits.get("monthly_unit_limits", {})
        azure_units = azure_limits.get("monthly_unit_limits", {})
        if user_input is not None:
            self._working_options.update(
                {
                    CONF_ROTATION_STRATEGY: user_input[CONF_ROTATION_STRATEGY],
                    CONF_AUTO_FAILOVER: user_input[CONF_AUTO_FAILOVER],
                    CONF_FAILOVER_ATTEMPTS: user_input[CONF_FAILOVER_ATTEMPTS],
                    CONF_FAILOVER_COOLDOWN: user_input[CONF_FAILOVER_COOLDOWN],
                    CONF_PROVIDER_LIMITS: {
                        PROVIDER_GOOGLE: {
                            "daily_request_limit": user_input[
                                "google_daily_request_limit"
                            ],
                            "monthly_request_limit": user_input[
                                "google_monthly_request_limit"
                            ],
                            "monthly_unit_limits": {
                                "*": user_input["google_monthly_token_limit"]
                            },
                        },
                        PROVIDER_AZURE: {
                            "daily_request_limit": user_input[
                                "azure_daily_request_limit"
                            ],
                            "monthly_request_limit": user_input[
                                "azure_monthly_request_limit"
                            ],
                            "monthly_unit_limits": {
                                "tts": user_input["azure_monthly_tts_character_limit"],
                                "stt": user_input["azure_monthly_stt_seconds_limit"],
                            },
                        },
                    },
                }
            )
            return await self.async_step_init()

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_ROTATION_STRATEGY,
                    default=self._working_options.get(
                        CONF_ROTATION_STRATEGY, DEFAULT_ROTATION_STRATEGY
                    ),
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=list(ROTATION_STRATEGIES),
                        translation_key=CONF_ROTATION_STRATEGY,
                    )
                ),
                vol.Required(
                    CONF_AUTO_FAILOVER,
                    default=self._working_options.get(CONF_AUTO_FAILOVER, True),
                ): bool,
                vol.Required(
                    CONF_FAILOVER_ATTEMPTS,
                    default=self._working_options.get(
                        CONF_FAILOVER_ATTEMPTS, DEFAULT_FAILOVER_ATTEMPTS
                    ),
                ): NumberSelector(NumberSelectorConfig(min=1, max=10, step=1)),
                vol.Required(
                    CONF_FAILOVER_COOLDOWN,
                    default=self._working_options.get(
                        CONF_FAILOVER_COOLDOWN, DEFAULT_FAILOVER_COOLDOWN
                    ),
                ): NumberSelector(NumberSelectorConfig(min=10, max=86400, step=10)),
                vol.Optional(
                    "google_daily_request_limit",
                    default=google_limits.get("daily_request_limit", 0),
                ): NumberSelector(NumberSelectorConfig(min=0, max=1000000, step=1)),
                vol.Optional(
                    "google_monthly_request_limit",
                    default=google_limits.get("monthly_request_limit", 0),
                ): NumberSelector(NumberSelectorConfig(min=0, max=10000000, step=1)),
                vol.Optional(
                    "google_monthly_token_limit",
                    default=google_units.get("*", 0),
                ): NumberSelector(
                    NumberSelectorConfig(min=0, max=1000000000, step=1000)
                ),
                vol.Optional(
                    "azure_daily_request_limit",
                    default=azure_limits.get("daily_request_limit", 0),
                ): NumberSelector(NumberSelectorConfig(min=0, max=1000000, step=1)),
                vol.Optional(
                    "azure_monthly_request_limit",
                    default=azure_limits.get("monthly_request_limit", 0),
                ): NumberSelector(NumberSelectorConfig(min=0, max=10000000, step=1)),
                vol.Optional(
                    "azure_monthly_tts_character_limit",
                    default=azure_units.get("tts", 0),
                ): NumberSelector(
                    NumberSelectorConfig(min=0, max=1000000000, step=1000)
                ),
                vol.Optional(
                    "azure_monthly_stt_seconds_limit",
                    default=azure_units.get("stt", 0),
                ): NumberSelector(NumberSelectorConfig(min=0, max=100000000, step=60)),
            }
        )
        return self.async_show_form(step_id="general", data_schema=schema)

    async def async_step_add_google(self, user_input=None) -> ConfigFlowResult:
        return await self._async_credential_form(PROVIDER_GOOGLE, user_input)

    async def async_step_add_azure(self, user_input=None) -> ConfigFlowResult:
        return await self._async_credential_form(PROVIDER_AZURE, user_input)

    async def async_step_manage_credentials(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        self._ensure_state()
        if not self._credentials:
            return self.async_abort(reason="no_credentials")
        options = [
            SelectOptionDict(
                value=item["id"],
                label=f"{item.get('name', item['id'])} ({item.get('provider')})",
            )
            for item in self._credentials
        ]
        if user_input is not None:
            self._editing_id = str(user_input[CONF_CREDENTIAL_ID])
            if user_input[CONF_CREDENTIAL_ACTION] == "delete":
                return await self.async_step_delete_credential()
            return await self.async_step_edit_credential()
        return self.async_show_form(
            step_id="manage_credentials",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CREDENTIAL_ID): SelectSelector(
                        SelectSelectorConfig(options=options)
                    ),
                    vol.Required(
                        CONF_CREDENTIAL_ACTION, default="edit"
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=["edit", "delete"],
                            translation_key=CONF_CREDENTIAL_ACTION,
                        )
                    ),
                }
            ),
        )

    async def async_step_edit_credential(self, user_input=None) -> ConfigFlowResult:
        self._ensure_state()
        current = next(
            item for item in self._credentials if item["id"] == self._editing_id
        )
        return await self._async_credential_form(
            str(current["provider"]), user_input, current=current
        )

    async def async_step_delete_credential(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        self._ensure_state()
        current = next(
            item for item in self._credentials if item["id"] == self._editing_id
        )
        if user_input is not None and user_input.get("confirm") is True:
            self._credentials = [
                item for item in self._credentials if item["id"] != self._editing_id
            ]
            self._editing_id = None
            return await self.async_step_init()
        return self.async_show_form(
            step_id="delete_credential",
            data_schema=vol.Schema({vol.Required("confirm", default=False): bool}),
            description_placeholders={"credential_name": current.get("name", "")},
        )

    async def _async_credential_form(
        self,
        provider: str,
        user_input: dict[str, Any] | None,
        *,
        current: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        self._ensure_state()
        current = current or {}
        errors: dict[str, str] = {}
        if user_input is not None:
            secret = str(user_input.get(CONF_API_KEY, "")).strip() or str(
                current.get("api_key", "")
            )
            region = str(user_input.get(CONF_AZURE_REGION, "")).strip().lower()
            if not secret:
                errors[CONF_API_KEY] = "key_required"
            if provider == PROVIDER_AZURE and not region:
                errors[CONF_AZURE_REGION] = "azure_region_required"
            if not errors:
                try:
                    if provider == PROVIDER_GOOGLE:
                        await validate_input(self.hass, {CONF_API_KEY: secret})
                    else:
                        await self.config_entry.runtime_data.providers.azure.async_validate(
                            key=secret, region=region
                        )
                except (APIError, ProviderError, Timeout):
                    errors["base"] = "invalid_auth"
            if not errors:
                item = {
                    "id": current.get("id", uuid4().hex),
                    "provider": provider,
                    "name": user_input[CONF_CREDENTIAL_NAME],
                    "api_key": secret,
                    "region": region if provider == PROVIDER_AZURE else None,
                    "enabled": user_input[CONF_ENABLED],
                    "priority": int(user_input[CONF_PRIORITY]),
                    "daily_request_limit": int(user_input[CONF_DAILY_REQUEST_LIMIT]),
                    "monthly_request_limit": int(
                        user_input[CONF_MONTHLY_REQUEST_LIMIT]
                    ),
                    "monthly_unit_limits": (
                        {"*": int(user_input[CONF_MONTHLY_TOKEN_LIMIT])}
                        if provider == PROVIDER_GOOGLE
                        else {
                            "tts": int(user_input[CONF_MONTHLY_TTS_CHARACTER_LIMIT]),
                            "stt": int(user_input[CONF_MONTHLY_STT_SECONDS_LIMIT]),
                        }
                    ),
                }
                self._credentials = [
                    existing
                    for existing in self._credentials
                    if existing.get("id") != item["id"]
                ] + [item]
                self._editing_id = None
                return await self.async_step_init()

        schema: dict[Any, Any] = {
            vol.Required(
                CONF_CREDENTIAL_NAME,
                default=current.get(
                    "name",
                    "Google" if provider == PROVIDER_GOOGLE else "Azure",
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
        limits = current.get("monthly_unit_limits", {})
        if provider == PROVIDER_GOOGLE:
            schema[
                vol.Optional(CONF_MONTHLY_TOKEN_LIMIT, default=limits.get("*", 0))
            ] = NumberSelector(NumberSelectorConfig(min=0, max=1000000000, step=1000))
        else:
            schema.update(
                {
                    vol.Required(
                        CONF_AZURE_REGION,
                        default=current.get(CONF_AZURE_REGION)
                        or current.get("region", DEFAULT_AZURE_REGION),
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
            step_id="edit_credential" if current else f"add_{provider}",
            data_schema=vol.Schema(schema),
            errors=errors,
        )

    async def async_step_save(self, user_input=None) -> ConfigFlowResult:
        self._ensure_state()
        if not any(
            item.get("provider") == PROVIDER_GOOGLE and item.get("enabled", True)
            for item in self._credentials
        ):
            return await self.async_step_google_required()
        self._working_options[CONF_CREDENTIALS] = self._credentials
        return self.async_create_entry(title="", data=self._working_options)

    async def async_step_google_required(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return await self.async_step_init()
        return self.async_show_form(
            step_id="google_required", data_schema=vol.Schema({})
        )


class LLMSubentryFlowHandler(ConfigSubentryFlow):
    """Flow for managing conversation subentries."""

    last_rendered_recommended = False
    last_rendered_provider = DEFAULT_PROVIDER

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
            self.last_rendered_provider = str(
                options.get(CONF_PROVIDER, DEFAULT_PROVIDER)
            )

        else:
            rendered_provider_matches = (
                user_input.get(CONF_PROVIDER, DEFAULT_PROVIDER)
                == self.last_rendered_provider
            )
            if (
                user_input[CONF_RECOMMENDED] == self.last_rendered_recommended
                and rendered_provider_matches
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

                capability = {
                    "conversation": ProviderCapability.CONVERSATION,
                    "stt": ProviderCapability.STT,
                    "tts": ProviderCapability.TTS,
                    "ai_task_data": ProviderCapability.AI_TASK,
                }[self._subentry_type]
                try:
                    await self._provider_hub.async_validate_options(
                        user_input, capability
                    )
                except ProviderError:
                    errors["base"] = "provider_credentials_required"

                if not errors:
                    if self._is_new:
                        return self.async_create_entry(
                            title=user_input.pop(CONF_NAME),
                            data=user_input,
                        )

                    return self.async_update_and_abort(
                        self._get_entry(),
                        self._get_reconfigure_subentry(),
                        data=user_input,
                    )

            # Re-render the options again, now with the recommended options shown/hidden
            self.last_rendered_recommended = user_input[CONF_RECOMMENDED]
            self.last_rendered_provider = str(
                user_input.get(CONF_PROVIDER, DEFAULT_PROVIDER)
            )

            options = user_input

        schema = await google_generative_ai_config_option_schema(
            self.hass,
            self._is_new,
            self._subentry_type,
            options,
            self._genai_client,
            self._provider_hub,
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
    provider_hub,
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

    provider = str(options.get(CONF_PROVIDER, DEFAULT_PROVIDER))
    capability = {
        "conversation": ProviderCapability.CONVERSATION,
        "stt": ProviderCapability.STT,
        "tts": ProviderCapability.TTS,
        "ai_task_data": ProviderCapability.AI_TASK,
    }[subentry_type]
    schema.update(
        {
            vol.Required(CONF_PROVIDER, default=provider): SelectSelector(
                SelectSelectorConfig(
                    mode=SelectSelectorMode.DROPDOWN,
                    options=provider_hub.available_providers(capability),
                    translation_key=CONF_PROVIDER,
                )
            )
        }
    )

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
        if provider == PROVIDER_AZURE:
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
        if provider == PROVIDER_AZURE:
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

    schema.update(
        {
            vol.Required(
                CONF_RECOMMENDED, default=options.get(CONF_RECOMMENDED, False)
            ): bool,
        }
    )

    if options.get(CONF_RECOMMENDED):
        return schema

    if provider == PROVIDER_AZURE:
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

    schema.update(
        {
            vol.Optional(
                CONF_CHAT_MODEL,
                description={"suggested_value": options.get(CONF_CHAT_MODEL)},
                default=default_model,
            ): SelectSelector(
                SelectSelectorConfig(mode=SelectSelectorMode.DROPDOWN, options=models)
            ),
            vol.Optional(
                CONF_TEMPERATURE,
                description={"suggested_value": options.get(CONF_TEMPERATURE)},
                default=RECOMMENDED_TEMPERATURE,
            ): NumberSelector(NumberSelectorConfig(min=0, max=2, step=0.05)),
        }
    )

    if subentry_type != "tts":
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
    if subentry_type == "conversation":
        schema.update(
            {
                vol.Optional(
                    CONF_USE_GOOGLE_SEARCH_TOOL,
                    description={
                        "suggested_value": options.get(CONF_USE_GOOGLE_SEARCH_TOOL),
                    },
                    default=RECOMMENDED_USE_GOOGLE_SEARCH_TOOL,
                ): bool,
            }
        )

    return schema
