# Modified for Luna Assistant.
# Derived from Home Assistant Core's Google Gemini integration,
# licensed under the Apache License 2.0.

"""Provider-aware AI Task integration for Luna Assistant Prime."""

from __future__ import annotations

from json import JSONDecodeError
from typing import TYPE_CHECKING, override

from google.genai.errors import APIError
from google.genai.types import GenerateContentConfig, Part, PartUnionDict
from homeassistant.components import ai_task, conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.json import json_loads

from .const import (
    CONF_IMAGE_MODEL,
    CONF_RECOMMENDED,
    LOGGER,
    RECOMMENDED_AI_TASK_MAX_TOKENS,
    RECOMMENDED_IMAGE_MODEL,
)
from .entity import (
    ERROR_GETTING_RESPONSE,
    LunaProviderLLMBaseEntity,
    async_prepare_files_for_prompt,
)
from .provider_hub import ProviderCapability, ProviderError

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigSubentry

    from . import LunaAssistantConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up AI Task entities."""
    for subentry in config_entry.subentries.values():
        if subentry.subentry_type != "ai_task_data":
            continue

        async_add_entities(
            [LunaAITaskEntity(config_entry, subentry)],
            config_subentry_id=subentry.subentry_id,
        )


class LunaAITaskEntity(
    ai_task.AITaskEntity,
    LunaProviderLLMBaseEntity,
):
    """Luna Provider Hub AI Task entity."""

    def __init__(
        self,
        entry: LunaAssistantConfigEntry,
        subentry: ConfigSubentry,
    ) -> None:
        """Initialize the entity."""
        super().__init__(entry, subentry)
        self._attr_supported_features = (
            ai_task.AITaskEntityFeature.GENERATE_DATA
            | ai_task.AITaskEntityFeature.SUPPORT_ATTACHMENTS
        )

        if self._provider_hub.available_providers(ProviderCapability.IMAGE):
            self._attr_supported_features |= ai_task.AITaskEntityFeature.GENERATE_IMAGE

    @override
    async def _async_generate_data(
        self,
        task: ai_task.GenDataTask,
        chat_log: conversation.ChatLog,
    ) -> ai_task.GenDataTaskResult:
        """Handle a generate data task."""
        await self._async_handle_chat_log(
            chat_log,
            task.structure,
            default_max_tokens=RECOMMENDED_AI_TASK_MAX_TOKENS,
            max_iterations=1000,
        )

        if not isinstance(chat_log.content[-1], conversation.AssistantContent):
            LOGGER.error(
                "Last content in chat log is not an AssistantContent: %s."
                " This could be due to the model not returning a valid response",
                chat_log.content[-1],
            )
            raise HomeAssistantError(ERROR_GETTING_RESPONSE)

        text = chat_log.content[-1].content or ""

        if not task.structure:
            return ai_task.GenDataTaskResult(
                conversation_id=chat_log.conversation_id,
                data=text,
            )

        try:
            data = json_loads(text)
        except JSONDecodeError as err:
            LOGGER.error(
                "Failed to parse JSON response: %s. Response: %s",
                err,
                text,
            )
            raise HomeAssistantError(ERROR_GETTING_RESPONSE) from err

        return ai_task.GenDataTaskResult(
            conversation_id=chat_log.conversation_id,
            data=data,
        )

    @override
    async def _async_generate_image(
        self,
        task: ai_task.GenImageTask,
        chat_log: conversation.ChatLog,
    ) -> ai_task.GenImageTaskResult:
        """Handle a generate image task."""
        # Get the user prompt from the chat log
        user_message = chat_log.content[-1]
        assert isinstance(user_message, conversation.UserContent)

        model = self.subentry.data.get(CONF_IMAGE_MODEL, RECOMMENDED_IMAGE_MODEL)

        async def generate(client):
            prompt_parts: list[PartUnionDict] = [user_message.content]
            if user_message.attachments:
                prompt_parts.extend(
                    await async_prepare_files_for_prompt(
                        self.hass,
                        client,
                        [(a.path, a.mime_type) for a in user_message.attachments],
                    )
                )
            return await client.aio.models.generate_content(
                model=model,
                contents=prompt_parts,
                config=GenerateContentConfig(response_modalities=["TEXT", "IMAGE"]),
            )

        try:
            response = await self._provider_hub.async_generate_image(generate)
        except (APIError, ProviderError, ValueError) as err:
            LOGGER.error("Error generating image: %s", err)
            raise HomeAssistantError(f"Error generating image: {err}") from err

        if response.prompt_feedback:
            raise HomeAssistantError(
                "Error generating content due to content"
                " violations, reason:"
                f" {response.prompt_feedback.block_reason_message}"
            )

        if (
            not response.candidates
            or not response.candidates[0].content
            or not response.candidates[0].content.parts
        ):
            raise HomeAssistantError("Unknown error generating image")

        # Parse response
        response_text = ""
        response_image: Part | None = None
        for part in response.candidates[0].content.parts:
            if (
                part.inline_data
                and part.inline_data.data
                and part.inline_data.mime_type
                and part.inline_data.mime_type.startswith("image/")
            ):
                if response_image is None:
                    response_image = part
                else:
                    LOGGER.warning("Prompt generated multiple images")
            elif isinstance(part.text, str) and not part.thought:
                response_text += part.text

        if response_image is None:
            raise HomeAssistantError("Response did not include image")

        assert response_image.inline_data is not None
        assert response_image.inline_data.data is not None
        assert response_image.inline_data.mime_type is not None

        image_data = response_image.inline_data.data
        mime_type = response_image.inline_data.mime_type

        chat_log.async_add_assistant_content_without_tools(
            conversation.AssistantContent(
                agent_id=self.entity_id,
                content=response_text,
            )
        )

        return ai_task.GenImageTaskResult(
            image_data=image_data,
            conversation_id=chat_log.conversation_id,
            mime_type=mime_type,
            model=model.partition("/")[-1],
        )
