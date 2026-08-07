# Modified for Luna Assistant.
# Derived from Home Assistant Core's Google Gemini integration,
# licensed under the Apache License 2.0.

"""Conversation support for the Luna Assistant integration."""

import time
from typing import Literal, override

from homeassistant.components import conversation
from homeassistant.components.tts import ATTR_MEDIA_PLAYER_ENTITY_ID
from homeassistant.components.tts.const import (
    ATTR_CACHE,
    ATTR_LANGUAGE,
    ATTR_MESSAGE,
    DOMAIN as TTS_DOMAIN,
)
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_LLM_HASS_API,
    CONF_PROMPT,
    MATCH_ALL,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    AUDIO_OUTPUT_ATOM,
    CONF_AUDIO_OUTPUT,
    CONF_LATENCY_PROFILE,
    CONF_OUTPUT_MEDIA_PLAYER,
    CONF_PERSONALITY,
    CONF_RESPONSE_LENGTH,
    DEFAULT_AUDIO_OUTPUT,
    DEFAULT_LATENCY_PROFILE,
    DEFAULT_PERSONALITY,
    DEFAULT_RESPONSE_LENGTH,
    DOMAIN,
    LATENCY_PROFILE_PROMPTS,
    LATENCY_PROFILE_TOOL_ITERATIONS,
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
        if subentry.subentry_type != "conversation":
            continue

        async_add_entities(
            [GoogleGenerativeAIConversationEntity(config_entry, subentry)],
            config_subentry_id=subentry.subentry_id,
        )


class GoogleGenerativeAIConversationEntity(
    conversation.ConversationEntity,
    conversation.AbstractConversationAgent,
    GoogleGenerativeAILLMBaseEntity,
):
    """Google Generative AI conversation agent."""

    _attr_supports_streaming = True

    def __init__(self, entry: ConfigEntry, subentry: ConfigSubentry) -> None:
        """Initialize the agent."""
        super().__init__(entry, subentry)
        if self.subentry.data.get(CONF_LLM_HASS_API):
            self._attr_supported_features = (
                conversation.ConversationEntityFeature.CONTROL
            )

    @property
    @override
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Return a list of supported languages."""
        return MATCH_ALL

    @override
    async def async_added_to_hass(self) -> None:
        """When entity is added to Home Assistant."""
        await super().async_added_to_hass()
        conversation.async_set_agent(self.hass, self.entry, self)

    @override
    async def async_will_remove_from_hass(self) -> None:
        """When entity will be removed from Home Assistant."""
        conversation.async_unset_agent(self.hass, self.entry)
        await super().async_will_remove_from_hass()

    @override
    async def _async_handle_message(
        self,
        user_input: conversation.ConversationInput,
        chat_log: conversation.ChatLog,
    ) -> conversation.ConversationResult:
        """Call the API."""
        options = self.subentry.data

        personality = options.get(CONF_PERSONALITY, DEFAULT_PERSONALITY)
        response_length = options.get(
            CONF_RESPONSE_LENGTH, DEFAULT_RESPONSE_LENGTH
        )
        latency_profile = options.get(CONF_LATENCY_PROFILE, DEFAULT_LATENCY_PROFILE)

        base_prompt = options.get(CONF_PROMPT, "")
        preset_prompt = " ".join(
            part
            for part in (
                PERSONALITY_PROMPTS.get(personality),
                RESPONSE_LENGTH_PROMPTS.get(response_length),
                LATENCY_PROFILE_PROMPTS.get(latency_profile),
            )
            if part
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

        await self._async_handle_chat_log(
            chat_log,
            max_iterations=LATENCY_PROFILE_TOOL_ITERATIONS.get(
                latency_profile, 10
            ),
        )

        result = conversation.async_get_result_from_chat_log(
            user_input, chat_log
        )
        await self._async_route_audio_output(result, user_input)
        return result

    async def _async_route_audio_output(
        self,
        result: conversation.ConversationResult,
        user_input: conversation.ConversationInput,
    ) -> None:
        """Route a voice reply to the configured external media player.

        Atom remains the default Assist Pipeline destination. For an external
        destination, Luna prefers the configured Microsoft legacy TTS service
        when it is available, and falls back to Luna TTS via ``tts.speak``.
        The selected media player is always addressed by its canonical
        ``entity_id``; the friendly name is never sent to a service call.

        Only after a TTS service call succeeds is the pipeline speech cleared.
        Any synchronous routing failure leaves the original speech untouched,
        so the Assist Pipeline falls back to the Atom.
        """
        options = self.subentry.data
        output_mode = options.get(CONF_AUDIO_OUTPUT, DEFAULT_AUDIO_OUTPUT)
        if output_mode == AUDIO_OUTPUT_ATOM:
            return

        # Do not make typed dashboard conversations unexpectedly speak aloud.
        # ESPHome/Assist voice requests provide a satellite or device context.
        if user_input.satellite_id is None and user_input.device_id is None:
            return

        configured_entity_id = options.get(CONF_OUTPUT_MEDIA_PLAYER)
        if not isinstance(configured_entity_id, str):
            LOGGER.warning(
                "External audio selected without a media player entity_id; "
                "falling back to Atom"
            )
            return

        media_player_state = self.hass.states.get(configured_entity_id)
        if (
            media_player_state is None
            or media_player_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN)
        ):
            LOGGER.warning(
                "Audio target entity_id %s is unavailable; falling back to Atom",
                configured_entity_id,
            )
            return

        # Use Home Assistant's canonical entity_id from the state object. Never
        # use the friendly name shown in the UI (for example, "Google Nest").
        target_entity_id = media_player_state.entity_id

        speech = result.response.speech.get("plain", {}).get("speech", "")
        if not isinstance(speech, str) or not speech.strip():
            return

        started = time.monotonic()
        provider: str | None = None
        if await self._async_route_with_microsoft_tts(
            target_entity_id, speech, user_input
        ):
            provider = "tts.microsoft_say"
        elif await self._async_route_with_luna_tts(
            target_entity_id, speech, user_input
        ):
            provider = "tts.speak / Luna TTS"

        if provider is None:
            LOGGER.warning(
                "No external TTS route succeeded for entity_id %s; "
                "falling back to Atom",
                target_entity_id,
            )
            return

        # The Nest owns playback from this point. Clear the pipeline speech and
        # return immediately so the satellite closes the previous Assist turn
        # and re-enables only its local micro wake word. Ordinary audio cannot
        # start STT; saying "Ei, Luna" invokes the barge-in service.
        result.response.speech.clear()
        LOGGER.info(
            "Luna audio routed to entity_id %s using %s; wake-word barge-in "
            "enabled; total %.0f ms",
            target_entity_id,
            provider,
            (time.monotonic() - started) * 1000,
        )

    async def _async_route_with_microsoft_tts(
        self,
        target_entity_id: str,
        speech: str,
        user_input: conversation.ConversationInput,
    ) -> bool:
        """Route through the legacy Microsoft TTS service when present."""
        service = "microsoft_say"
        if not self.hass.services.has_service(TTS_DOMAIN, service):
            return False

        try:
            await self.hass.services.async_call(
                TTS_DOMAIN,
                service,
                {
                    # This is deliberately the media_player entity_id, not its
                    # friendly/display name.
                    ATTR_ENTITY_ID: target_entity_id,
                    ATTR_MESSAGE: speech,
                    ATTR_CACHE: True,
                },
                blocking=True,
                context=user_input.context,
            )
        except Exception:  # noqa: BLE001
            LOGGER.exception(
                "Microsoft TTS routing to entity_id %s failed; trying Luna TTS",
                target_entity_id,
            )
            return False

        return True

    async def _async_route_with_luna_tts(
        self,
        target_entity_id: str,
        speech: str,
        user_input: conversation.ConversationInput,
    ) -> bool:
        """Route through Luna's TTS entity as a compatibility fallback."""
        tts_entity_id = self._async_find_luna_tts_entity_id()
        if tts_entity_id is None:
            return False

        try:
            await self.hass.services.async_call(
                TTS_DOMAIN,
                "speak",
                {
                    ATTR_ENTITY_ID: tts_entity_id,
                    ATTR_MEDIA_PLAYER_ENTITY_ID: target_entity_id,
                    ATTR_MESSAGE: speech,
                    ATTR_CACHE: True,
                    ATTR_LANGUAGE: (
                        user_input.language or self.hass.config.language
                    ),
                },
                blocking=True,
                context=user_input.context,
            )
        except Exception:  # noqa: BLE001
            LOGGER.exception(
                "Luna TTS routing to entity_id %s failed; falling back to Atom",
                target_entity_id,
            )
            return False

        return True

    def _async_find_luna_tts_entity_id(self) -> str | None:
        """Return the first enabled Luna TTS entity for this config entry."""
        entity_registry = er.async_get(self.hass)
        for subentry in self.entry.subentries.values():
            if subentry.subentry_type != "tts":
                continue
            entity_id = entity_registry.async_get_entity_id(
                TTS_DOMAIN,
                DOMAIN,
                subentry.subentry_id,
            )
            if entity_id is not None:
                return entity_id
        return None
