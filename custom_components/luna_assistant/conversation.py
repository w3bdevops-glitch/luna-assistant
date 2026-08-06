# Modified for Luna Assistant.
# Derived from Home Assistant Core's Google Gemini integration,
# licensed under the Apache License 2.0.

"""Conversation support for Luna Assistant."""

from typing import Any, Literal, override

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import ATTR_ENTITY_ID, CONF_LLM_HASS_API, CONF_PROMPT, MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    AUDIO_OUTPUT_EXTERNAL,
    CONF_AUDIO_OUTPUT,
    CONF_EXTERNAL_ANNOUNCE,
    CONF_EXTERNAL_VOLUME,
    CONF_FALLBACK_TO_ATOM,
    CONF_LATENCY_PROFILE,
    CONF_MEDIA_PLAYER_ENTITY_ID,
    CONF_PERSONALITY,
    CONF_RESPONSE_LENGTH,
    DEFAULT_AUDIO_OUTPUT,
    DEFAULT_EXTERNAL_ANNOUNCE,
    DEFAULT_EXTERNAL_VOLUME,
    DEFAULT_FALLBACK_TO_ATOM,
    DEFAULT_LATENCY_PROFILE,
    DEFAULT_PERSONALITY,
    DEFAULT_RESPONSE_LENGTH,
    DOMAIN,
    LATENCY_PROFILE_PROMPTS,
    LOGGER,
    PERSONALITY_PROMPTS,
    RESPONSE_LENGTH_PROMPTS,
)
from .entity import GoogleGenerativeAILLMBaseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up conversation entities."""
    for subentry in config_entry.subentries.values():
        if subentry.subentry_type == "conversation":
            async_add_entities(
                [GoogleGenerativeAIConversationEntity(config_entry, subentry)],
                config_subentry_id=subentry.subentry_id,
            )


class GoogleGenerativeAIConversationEntity(
    conversation.ConversationEntity,
    conversation.AbstractConversationAgent,
    GoogleGenerativeAILLMBaseEntity,
):
    """Luna conversation agent with selectable audio output."""

    _attr_supports_streaming = True

    def __init__(self, entry: ConfigEntry, subentry: ConfigSubentry) -> None:
        super().__init__(entry, subentry)
        if self.subentry.data.get(CONF_LLM_HASS_API):
            self._attr_supported_features = conversation.ConversationEntityFeature.CONTROL

    @property
    @override
    def supported_languages(self) -> list[str] | Literal["*"]:
        return MATCH_ALL

    @override
    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        conversation.async_set_agent(self.hass, self.entry, self)

    @override
    async def async_will_remove_from_hass(self) -> None:
        conversation.async_unset_agent(self.hass, self.entry)
        await super().async_will_remove_from_hass()

    @override
    async def _async_handle_message(
        self,
        user_input: conversation.ConversationInput,
        chat_log: conversation.ChatLog,
    ) -> conversation.ConversationResult:
        options = self.subentry.data
        await self._async_stop_external_player(options, user_input.context)

        personality = options.get(CONF_PERSONALITY, DEFAULT_PERSONALITY)
        response_length = options.get(CONF_RESPONSE_LENGTH, DEFAULT_RESPONSE_LENGTH)
        latency_profile = options.get(CONF_LATENCY_PROFILE, DEFAULT_LATENCY_PROFILE)
        base_prompt = options.get(CONF_PROMPT, "")
        preset_prompt = " ".join(
            part for part in (
                PERSONALITY_PROMPTS.get(personality),
                RESPONSE_LENGTH_PROMPTS.get(response_length),
                LATENCY_PROFILE_PROMPTS.get(latency_profile),
            ) if part
        )
        effective_prompt = f"{base_prompt} {preset_prompt}".strip()

        try:
            await chat_log.async_provide_llm_data(
                user_input.as_llm_context(DOMAIN),
                options.get(CONF_LLM_HASS_API),
                effective_prompt,
                user_input.extra_system_prompt,
            )
        except conversation.ConverseError as err:
            return err.as_conversation_result()

        await self._async_handle_chat_log(chat_log)
        result = conversation.async_get_result_from_chat_log(user_input, chat_log)

        if options.get(CONF_AUDIO_OUTPUT, DEFAULT_AUDIO_OUTPUT) != AUDIO_OUTPUT_EXTERNAL:
            return result

        player = options.get(CONF_MEDIA_PLAYER_ENTITY_ID)
        speech = _extract_plain_speech(result)
        if not player or not speech:
            if options.get(CONF_FALLBACK_TO_ATOM, DEFAULT_FALLBACK_TO_ATOM):
                return result
            result.response.async_set_speech("")
            return result

        tts_entity = self._find_luna_tts_entity_id()
        if tts_entity is None:
            LOGGER.error("No Luna TTS entity found for external audio routing")
            if options.get(CONF_FALLBACK_TO_ATOM, DEFAULT_FALLBACK_TO_ATOM):
                return result
            result.response.async_set_speech("")
            return result

        try:
            volume = max(0.0, min(1.0, float(
                options.get(CONF_EXTERNAL_VOLUME, DEFAULT_EXTERNAL_VOLUME)
            )))
            await self.hass.services.async_call(
                "media_player",
                "volume_set",
                {ATTR_ENTITY_ID: player, "volume_level": volume},
                blocking=True,
                context=user_input.context,
            )
            await self.hass.services.async_call(
                "tts",
                "speak",
                {
                    ATTR_ENTITY_ID: tts_entity,
                    "media_player_entity_id": player,
                    "message": speech,
                    "cache": True,
                    "options": {
                        "announce": bool(options.get(
                            CONF_EXTERNAL_ANNOUNCE, DEFAULT_EXTERNAL_ANNOUNCE
                        ))
                    },
                },
                blocking=False,
                context=user_input.context,
            )
        except Exception:
            LOGGER.exception("Unable to route Luna speech to %s", player)
            if options.get(CONF_FALLBACK_TO_ATOM, DEFAULT_FALLBACK_TO_ATOM):
                return result

        result.response.async_set_speech("")
        return result

    async def _async_stop_external_player(
        self, options: dict[str, Any], context: Any
    ) -> None:
        if options.get(CONF_AUDIO_OUTPUT, DEFAULT_AUDIO_OUTPUT) != AUDIO_OUTPUT_EXTERNAL:
            return
        player = options.get(CONF_MEDIA_PLAYER_ENTITY_ID)
        if not player:
            return
        try:
            await self.hass.services.async_call(
                "media_player",
                "media_stop",
                {ATTR_ENTITY_ID: player},
                blocking=False,
                context=context,
            )
        except Exception:
            LOGGER.debug("External player %s did not accept media_stop", player)

    def _find_luna_tts_entity_id(self) -> str | None:
        registry = er.async_get(self.hass)
        for item in er.async_entries_for_config_entry(registry, self.entry.entry_id):
            if item.domain == "tts":
                return item.entity_id
        return None


def _extract_plain_speech(result: conversation.ConversationResult) -> str:
    speech = getattr(result.response, "speech", None)
    if isinstance(speech, dict):
        plain = speech.get("plain")
        if isinstance(plain, dict):
            value = plain.get("speech")
            return value if isinstance(value, str) else ""
    return ""
