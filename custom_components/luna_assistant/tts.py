# Modified for Luna Assistant.
# Derived from Home Assistant Core's Google Gemini integration,
# licensed under the Apache License 2.0.

"""Provider-aware text-to-speech support for Luna Assistant Prime."""

from collections.abc import Mapping
from typing import Any, override

from propcache.api import cached_property

from homeassistant.components.tts import (
    ATTR_VOICE,
    TextToSpeechEntity,
    TtsAudioType,
    Voice,
)
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import CONF_PROMPT
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_CHAT_MODEL,
    CONF_PROVIDER,
    CONF_SPEAKING_PACE,
    CONF_VOICE_MOOD,
    CONF_TEMPERATURE,
    LOGGER,
    DEFAULT_SPEAKING_PACE,
    DEFAULT_TTS_STYLE_PROMPT,
    DEFAULT_VOICE_MOOD,
    DEFAULT_PROVIDER,
    PROVIDER_AZURE,
    AZURE_PT_BR_VOICES,
    SPEAKING_PACE_PROMPTS,
    VOICE_MOOD_PROMPTS,
    RECOMMENDED_TEMPERATURE,
    RECOMMENDED_TTS_MODEL,
)
from .entity import LunaProviderLLMBaseEntity
from .provider_hub import ProviderError


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up TTS entities."""
    for subentry in config_entry.subentries.values():
        if subentry.subentry_type != "tts":
            continue

        async_add_entities(
            [LunaTextToSpeechEntity(config_entry, subentry)],
            config_subentry_id=subentry.subentry_id,
        )


class LunaTextToSpeechEntity(
    TextToSpeechEntity, LunaProviderLLMBaseEntity
):
    """Luna Provider Hub text-to-speech entity."""

    _attr_supported_options = [ATTR_VOICE]
    # See https://ai.google.dev/gemini-api/docs/speech-generation#languages
    # Note the documentation might not be up to date, e.g. el-GR is not listed
    # there but is supported.
    _attr_supported_languages = [
        "af-ZA",
        "am-ET",
        "ar-EG",
        "az-AZ",
        "be-BY",
        "bg-BG",
        "bn-BD",
        "ca-ES",
        "ceb-PH",
        "cmn-CN",
        "cs-CZ",
        "da-DK",
        "de-DE",
        "el-GR",
        "en-IN",
        "en-US",
        "es-ES",
        "es-US",
        "et-EE",
        "eu-ES",
        "fa-IR",
        "fi-FI",
        "fil-PH",
        "fr-FR",
        "gl-ES",
        "gu-IN",
        "he-IL",
        "hi-IN",
        "hr-HR",
        "ht-HT",
        "hu-HU",
        "hy-AM",
        "id-ID",
        "is-IS",
        "it-IT",
        "ja-JP",
        "jv-ID",
        "ka-GE",
        "kn-IN",
        "ko-KR",
        "kok-IN",
        "la-VA",
        "lb-LU",
        "lo-LA",
        "lt-LT",
        "lv-LV",
        "mai-IN",
        "mg-MG",
        "mk-MK",
        "ml-IN",
        "mn-MN",
        "mr-IN",
        "ms-MY",
        "my-MM",
        "nb-NO",
        "ne-NP",
        "nl-NL",
        "nn-NO",
        "or-IN",
        "pa-IN",
        "pl-PL",
        "ps-AF",
        "pt-BR",
        "pt-PT",
        "ro-RO",
        "ru-RU",
        "sd-PK",
        "si-LK",
        "sk-SK",
        "sl-SI",
        "sq-AL",
        "sr-RS",
        "sv-SE",
        "sw-KE",
        "ta-IN",
        "te-IN",
        "th-TH",
        "tr-TR",
        "uk-UA",
        "ur-PK",
        "vi-VN",
    ]
    # Unused, but required by base class.
    # The Gemini TTS models detect the input language automatically.
    _attr_default_language = "en-US"
    # See https://ai.google.dev/gemini-api/docs/speech-generation#voices
    _google_voices = [
        Voice(voice.split(" ", 1)[0].lower(), voice)
        for voice in (
            "Zephyr (Bright)",
            "Puck (Upbeat)",
            "Charon (Informative)",
            "Kore (Firm)",
            "Fenrir (Excitable)",
            "Leda (Youthful)",
            "Orus (Firm)",
            "Aoede (Breezy)",
            "Callirrhoe (Easy-going)",
            "Autonoe (Bright)",
            "Enceladus (Breathy)",
            "Iapetus (Clear)",
            "Umbriel (Easy-going)",
            "Algieba (Smooth)",
            "Despina (Smooth)",
            "Erinome (Clear)",
            "Algenib (Gravelly)",
            "Rasalgethi (Informative)",
            "Laomedeia (Upbeat)",
            "Achernar (Soft)",
            "Alnilam (Firm)",
            "Schedar (Even)",
            "Gacrux (Mature)",
            "Pulcherrima (Forward)",
            "Achird (Friendly)",
            "Zubenelgenubi (Casual)",
            "Vindemiatrix (Gentle)",
            "Sadachbia (Lively)",
            "Sadaltager (Knowledgeable)",
            "Sulafat (Warm)",
        )
    ]

    def __init__(self, config_entry: ConfigEntry, subentry: ConfigSubentry) -> None:
        """Initialize the TTS entity."""
        super().__init__(config_entry, subentry, RECOMMENDED_TTS_MODEL)
        if subentry.data.get(CONF_PROVIDER, DEFAULT_PROVIDER) == PROVIDER_AZURE:
            self._supported_voices = [Voice(voice, voice) for voice in AZURE_PT_BR_VOICES]
        else:
            self._supported_voices = self._google_voices

    @callback
    @override
    def async_get_supported_voices(self, language: str) -> list[Voice]:
        """Return a list of supported voices for a language."""
        return self._supported_voices

    @cached_property
    @override
    def default_options(self) -> Mapping[str, Any]:
        """Return a mapping with the default options."""
        return {
            ATTR_VOICE: self._supported_voices[0].voice_id,
        }

    @override
    async def async_get_tts_audio(
        self, message: str, language: str, options: dict[str, Any]
    ) -> TtsAudioType:
        """Generate one provider-neutral validated WAV response."""
        if not message.strip():
            raise HomeAssistantError("Luna TTS received an empty message")

        model = self.subentry.data.get(CONF_CHAT_MODEL, RECOMMENDED_TTS_MODEL)
        if model in {
            "gemini-2.5-flash-preview-tts",
            "models/gemini-2.5-flash-preview-tts",
        }:
            LOGGER.warning(
                "Using Gemini 3.1 TTS instead of legacy configured model %s",
                model,
            )
            model = RECOMMENDED_TTS_MODEL

        voice_name = options.get(ATTR_VOICE, self._supported_voices[0].voice_id)

        style_prompt = self.subentry.data.get(
            CONF_PROMPT, DEFAULT_TTS_STYLE_PROMPT
        )
        voice_mood = self.subentry.data.get(
            CONF_VOICE_MOOD, DEFAULT_VOICE_MOOD
        )
        speaking_pace = self.subentry.data.get(
            CONF_SPEAKING_PACE, DEFAULT_SPEAKING_PACE
        )
        mood_text = VOICE_MOOD_PROMPTS.get(voice_mood, "")
        pace_text = SPEAKING_PACE_PROMPTS.get(speaking_pace, "")
        full_style = " ".join(
            part.strip()
            for part in (
                style_prompt,
                f"Use uma interpretação {mood_text}. {pace_text}",
            )
            if isinstance(part, str) and part.strip()
        )
        try:
            result = await self._provider_hub.async_synthesize_tts(
                options=self.subentry.data,
                message=message,
                language=language,
                voice=voice_name,
                model=model,
                temperature=self.subentry.data.get(
                    CONF_TEMPERATURE, RECOMMENDED_TEMPERATURE
                ),
                style_prompt=full_style,
                speaking_pace=speaking_pace,
            )
        except ProviderError as exc:
            LOGGER.error("Luna TTS failed: %s", exc, exc_info=True)
            raise HomeAssistantError(str(exc)) from exc

        LOGGER.info(
            "Luna TTS valid: provider=%s model=%s voice=%s "
            "wav_bytes=%d rate=%dHz channels=%d bits=%d",
            result.provider,
            model,
            result.voice,
            len(result.data),
            result.sample_rate,
            result.channels,
            result.bits_per_sample,
        )
        return result.format, result.data
