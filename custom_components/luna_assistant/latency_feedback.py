"""Pre-generate and rotate local spoken feedback while Search is running."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from functools import partial
from hashlib import sha256
from pathlib import Path
from random import SystemRandom
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.storage import Store

from .const import (
    CONF_CHAT_MODEL,
    CONF_LATENCY_FEEDBACK_DELAY_MS,
    CONF_LATENCY_FEEDBACK_ENABLED,
    CONF_LATENCY_PHRASES,
    CONF_OUTPUT_MEDIA_PLAYER,
    CONF_PROMPT,
    CONF_SPEAKING_PACE,
    CONF_TEMPERATURE,
    CONF_VOICE_MOOD,
    DEFAULT_LATENCY_FEEDBACK_DELAY_MS,
    DEFAULT_LATENCY_PHRASES,
    DEFAULT_SPEAKING_PACE,
    DEFAULT_TTS_STYLE_PROMPT,
    DEFAULT_VOICE_MOOD,
    RECOMMENDED_TEMPERATURE,
    RECOMMENDED_TTS_MODEL,
)
from .provider_hub import LunaProviderHub, ProviderCapability, ProviderError

STORE_VERSION = 1
STORE_KEY_PREFIX = "luna_assistant_latency_feedback"


class LatencyFeedback:
    """Own the phrase catalog, generated audio and shuffle-bag playback."""

    def __init__(self, hass, entry: ConfigEntry, providers: LunaProviderHub) -> None:
        self._hass = hass
        self._entry = entry
        self._providers = providers
        self._settings = {**entry.data, **entry.options}
        self._store: Store[dict[str, Any]] = Store(
            hass, STORE_VERSION, f"{STORE_KEY_PREFIX}_{entry.entry_id}"
        )
        self._catalog: dict[str, dict[str, Any]] = {}
        self._bag: list[str] = []
        self._last_phrase: str | None = None
        self._generation_lock = asyncio.Lock()

    @classmethod
    async def async_create(
        cls, hass, entry: ConfigEntry, providers: LunaProviderHub
    ) -> LatencyFeedback:
        feedback = cls(hass, entry, providers)
        loaded = await feedback._store.async_load()
        if isinstance(loaded, Mapping):
            feedback._catalog = {
                str(key): dict(value)
                for key, value in loaded.get("catalog", {}).items()
                if isinstance(value, Mapping)
            }
        return feedback

    @property
    def enabled(self) -> bool:
        return bool(self._settings.get(CONF_LATENCY_FEEDBACK_ENABLED, True))

    @property
    def phrases(self) -> tuple[str, ...]:
        raw = self._settings.get(CONF_LATENCY_PHRASES, DEFAULT_LATENCY_PHRASES)
        if isinstance(raw, str):
            values = raw.splitlines()
        else:
            values = raw if isinstance(raw, (list, tuple)) else DEFAULT_LATENCY_PHRASES
        result: list[str] = []
        for value in values:
            phrase = str(value).strip()
            if phrase and phrase not in result:
                result.append(phrase)
        return tuple(result or DEFAULT_LATENCY_PHRASES)

    def _tts_options(self) -> dict[str, Any]:
        for subentry in self._entry.subentries.values():
            if subentry.subentry_type == "tts":
                return dict(subentry.data)
        return {}

    def _config_hash(self, phrase: str, options: Mapping[str, Any]) -> str:
        route = ",".join(self._providers.credentials.route_for(ProviderCapability.TTS))
        material = "|".join(
            (
                phrase,
                route,
                str(options.get(CONF_CHAT_MODEL, RECOMMENDED_TTS_MODEL)),
                str(options.get(CONF_VOICE_MOOD, DEFAULT_VOICE_MOOD)),
                str(options.get(CONF_SPEAKING_PACE, DEFAULT_SPEAKING_PACE)),
                str(options.get(CONF_PROMPT, DEFAULT_TTS_STYLE_PROMPT)),
            )
        )
        return sha256(material.encode("utf-8")).hexdigest()

    def _media_dir(self) -> Path:
        return Path(self._hass.config.path("media", "luna_assistant", "latency"))

    async def async_prepare_defaults(self) -> None:
        """Generate missing default files after startup without blocking setup."""
        if not self.enabled or not self._providers.credentials.route_for(
            ProviderCapability.TTS
        ):
            return
        await self.async_generate()

    async def async_generate(self) -> dict[str, int]:
        """Generate only missing or stale phrases through the configured TTS route."""
        async with self._generation_lock:
            options = self._tts_options()
            generated = skipped = failed = 0
            media_dir = self._media_dir()
            await self._hass.async_add_executor_job(
                partial(media_dir.mkdir, parents=True, exist_ok=True)
            )
            for phrase in self.phrases:
                digest = self._config_hash(phrase, options)
                path = media_dir / f"{digest[:20]}.wav"
                current = self._catalog.get(phrase, {})
                exists = await self._hass.async_add_executor_job(path.exists)
                if current.get("hash") == digest and exists:
                    skipped += 1
                    continue
                try:
                    audio = await self._providers.async_synthesize_tts(
                        options=options,
                        message=phrase,
                        language="pt-BR",
                        voice=str(options.get("voice", "zephyr")),
                        model=str(options.get(CONF_CHAT_MODEL, RECOMMENDED_TTS_MODEL)),
                        temperature=float(
                            options.get(CONF_TEMPERATURE, RECOMMENDED_TEMPERATURE)
                        ),
                        style_prompt=str(
                            options.get(CONF_PROMPT, DEFAULT_TTS_STYLE_PROMPT)
                        ),
                        speaking_pace=str(
                            options.get(CONF_SPEAKING_PACE, DEFAULT_SPEAKING_PACE)
                        ),
                    )
                    await self._hass.async_add_executor_job(
                        path.write_bytes, audio.data
                    )
                except (ProviderError, OSError, ValueError) as err:
                    failed += 1
                    self._catalog[phrase] = {
                        "hash": digest,
                        "status": "error",
                        "error": type(err).__name__,
                    }
                    continue
                self._catalog[phrase] = {
                    "hash": digest,
                    "status": "generated",
                    "filename": path.name,
                    "provider": audio.provider,
                    "voice": audio.voice,
                }
                generated += 1
            await self._store.async_save({"catalog": self._catalog})
            self._bag.clear()
            return {"generated": generated, "skipped": skipped, "failed": failed}

    def _ready_phrases(self) -> list[str]:
        return [
            phrase
            for phrase in self.phrases
            if self._catalog.get(phrase, {}).get("status") == "generated"
            and self._catalog.get(phrase, {}).get("filename")
        ]

    def _next_phrase(self) -> str | None:
        ready = self._ready_phrases()
        if not ready:
            return None
        if not self._bag:
            self._bag = ready[:]
            SystemRandom().shuffle(self._bag)
            if len(self._bag) > 1 and self._bag[-1] == self._last_phrase:
                self._bag[0], self._bag[-1] = self._bag[-1], self._bag[0]
        phrase = self._bag.pop()
        if phrase == self._last_phrase and self._bag:
            replacement = self._bag.pop()
            self._bag.insert(0, phrase)
            phrase = replacement
        self._last_phrase = phrase
        return phrase

    async def async_play_phrase(self, phrase: str, media_player: str | None) -> bool:
        """Play a generated file on the configured external voice player."""
        if not media_player:
            return False
        item = self._catalog.get(phrase, {})
        filename = item.get("filename")
        if item.get("status") != "generated" or not filename:
            return False
        await self._hass.services.async_call(
            "media_player",
            "play_media",
            {
                "media_content_id": (
                    "media-source://media_source/local/"
                    f"luna_assistant/latency/{filename}"
                ),
                "media_content_type": "music",
            },
            target={"entity_id": media_player},
            blocking=False,
        )
        return True

    def _resolve_media_player(
        self, options: Mapping[str, Any], device_id: str | None
    ) -> str | None:
        configured = str(options.get(CONF_OUTPUT_MEDIA_PLAYER, "")).strip()
        if configured:
            return configured
        if not device_id:
            return None
        registry = er.async_get(self._hass)
        candidates = [
            entry.entity_id
            for entry in er.async_entries_for_device(
                registry, device_id, include_disabled_entities=False
            )
            if entry.domain == "media_player"
        ]
        return sorted(candidates)[0] if candidates else None

    async def async_play_next(
        self, options: Mapping[str, Any], device_id: str | None = None
    ) -> bool:
        phrase = self._next_phrase()
        return bool(
            phrase
            and await self.async_play_phrase(
                phrase, self._resolve_media_player(options, device_id)
            )
        )

    async def async_mask_latency(
        self,
        task: asyncio.Task,
        options: Mapping[str, Any],
        device_id: str | None = None,
    ) -> None:
        """Play one local filler only when the Search task exceeds the threshold."""
        if not self.enabled:
            return
        delay = max(
            0,
            int(
                self._settings.get(
                    CONF_LATENCY_FEEDBACK_DELAY_MS,
                    DEFAULT_LATENCY_FEEDBACK_DELAY_MS,
                )
            ),
        )
        done, _pending = await asyncio.wait({task}, timeout=delay / 1000)
        if not done:
            await self.async_play_next(options, device_id)

    def diagnostics(self) -> dict[str, Any]:
        statuses: dict[str, int] = {}
        for phrase in self.phrases:
            status = self._catalog.get(phrase, {}).get("status", "pending")
            statuses[status] = statuses.get(status, 0) + 1
        return {
            "enabled": self.enabled,
            "delay_ms": int(
                self._settings.get(
                    CONF_LATENCY_FEEDBACK_DELAY_MS,
                    DEFAULT_LATENCY_FEEDBACK_DELAY_MS,
                )
            ),
            "phrase_count": len(self.phrases),
            "statuses": statuses,
            "rotation": "shuffle_bag_without_immediate_repetition",
        }
