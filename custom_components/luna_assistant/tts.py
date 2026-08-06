# Modified for Luna Assistant.
# Derived from Home Assistant Core's Google Gemini integration,
# licensed under the Apache License 2.0.

"""Text-to-speech support for Luna Assistant."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, override

from google.genai import types
from google.genai.errors import APIError, ClientError
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
    CONF_SPEAKING_PACE,
    CONF_TEMPERATURE,
    CONF_VOICE_MOOD,
    DEFAULT_SPEAKING_PACE,
    DEFAULT_TTS_STYLE_PROMPT,
    DEFAULT_VOICE_MOOD,
    LOGGER,
    RECOMMENDED_TEMPERATURE,
    RECOMMENDED_TTS_MODEL,
    SPEAKING_PACE_PROMPTS,
    VOICE_MOOD_PROMPTS,
)
from .entity import GoogleGenerativeAILLMBaseEntity
from .helpers import (
    convert_to_wav,
    extract_audio_parts,
    validate_wav,
)

_LEGACY_TTS_MODELS = {
    "gemini-2.5-flash-preview-tts",
    "models/gemini-2.5-flash-preview-tts",
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Luna TTS entities."""
    for subentry in config_entry.subentries.values():
        if subentry.subentry_type != "tts":
            continue

        async_add_entities(
            [GoogleGenerativeAITextToSpeechEntity(config_entry, subentry)],
            config_subentry_id=subentry.subentry_id,
        )


class GoogleGenerativeAITextToSpeechEntity(
    TextToSpeechEntity, GoogleGenerativeAILLMBaseEntity
):
    """Luna Gemini text-to-speech entity."""

    _attr_supported_options = [ATTR_VOICE]

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

    # Gemini detects the input language automatically.
    _attr_default_language = "pt-BR"

    _supported_voices = [
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
        """Initialize Luna TTS."""
        super().__init__(config_entry, subentry, RECOMMENDED_TTS_MODEL)

    @callback
    @override
    def async_get_supported_voices(self, language: str) -> list[Voice]:
        """Return supported voices."""
        return self._supported_voices

    @cached_property
    @override
    def default_options(self) -> Mapping[str, Any]:
        """Return default TTS options."""
        return {ATTR_VOICE: self._supported_voices[0].voice_id}

    @override
    async def async_get_tts_audio(
        self, message: str, language: str, options: dict[str, Any]
    ) -> TtsAudioType:
        """Generate, validate and return WAV audio."""
        if not message.strip():
            raise HomeAssistantError("Luna TTS received an empty message")

        model = self.subentry.data.get(CONF_CHAT_MODEL, RECOMMENDED_TTS_MODEL)
        if model in _LEGACY_TTS_MODELS:
            LOGGER.warning(
                "Migrating Luna TTS request from legacy model %s to %s",
                model,
                RECOMMENDED_TTS_MODEL,
            )
            model = RECOMMENDED_TTS_MODEL

        voice_name = options.get(
            ATTR_VOICE, self._supported_voices[0].voice_id
        )

        config = types.GenerateContentConfig(
            temperature=self.subentry.data.get(
                CONF_TEMPERATURE, RECOMMENDED_TEMPERATURE
            ),
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=voice_name
                    )
                )
            ),
        )

        styled_message = self._build_tts_prompt(message)
        attempts = (styled_message, message) if styled_message != message else (message,)
        last_error: Exception | None = None

        for attempt_number, prompt in enumerate(attempts, start=1):
            try:
                response = await self._genai_client.aio.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=config,
                )
                pcm_audio, mime_type = extract_audio_parts(response)
                wav_audio = convert_to_wav(pcm_audio, mime_type)
                wav_info = validate_wav(wav_audio)

                LOGGER.info(
                    "Luna TTS audio valid: model=%s voice=%s mime=%s "
                    "source_bytes=%d wav_bytes=%d rate=%dHz channels=%d "
                    "bits=%d duration=%.2fs attempt=%d",
                    model,
                    voice_name,
                    mime_type,
                    len(pcm_audio),
                    len(wav_audio),
                    wav_info.sample_rate,
                    wav_info.channels,
                    wav_info.bits_per_sample,
                    wav_info.duration_seconds,
                    attempt_number,
                )
                return "wav", wav_audio

            except (ValueError, TypeError, HomeAssistantError) as exc:
                last_error = exc
                if attempt_number < len(attempts):
                    LOGGER.warning(
                        "Luna TTS returned invalid audio on attempt %d; "
                        "retrying without style instructions: %s",
                        attempt_number,
                        exc,
                    )
                    continue
                break
            except (APIError, ClientError) as exc:
                LOGGER.error("Gemini TTS API error: %s", exc, exc_info=True)
                raise HomeAssistantError(str(exc)) from exc

        LOGGER.error("Luna TTS could not produce valid audio: %s", last_error)
        raise HomeAssistantError(
            f"Luna TTS could not produce valid audio: {last_error}"
        ) from last_error

    def _build_tts_prompt(self, message: str) -> str:
        """Build a prompt that clearly separates direction from transcript."""
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
        preset_style = f"Use uma interpretação {mood_text}. {pace_text}".strip()
        full_style = " ".join(
            part.strip()
            for part in (style_prompt, preset_style)
            if isinstance(part, str) and part.strip()
        )

        if not full_style:
            return message

        return (
            f"{full_style}\n\n"
            "Leia somente o texto entre as marcas TRANSCRIÇÃO. "
            "Não leia as instruções nem as marcas.\n"
            "=== TRANSCRIÇÃO ===\n"
            f"{message}\n"
            "=== FIM DA TRANSCRIÇÃO ==="
        )
