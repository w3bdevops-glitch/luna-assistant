# Modified for Luna Assistant.
# Derived from Home Assistant Core's Google Gemini integration,
# licensed under the Apache License 2.0.

"""The Luna Assistant integration."""

from functools import partial
from types import MappingProxyType

from google.genai import Client
from google.genai.errors import APIError, ClientError
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.helpers import (
    config_validation as cv,
)
from homeassistant.helpers import (
    device_registry as dr,
)
from homeassistant.helpers import (
    entity_registry as er,
)
from homeassistant.helpers.typing import UNDEFINED, ConfigType, UndefinedType
from requests.exceptions import Timeout

from .const import (
    AUDIO_OUTPUT_ATOM,
    CONF_AUDIO_OUTPUT,
    CONF_OUTPUT_MEDIA_PLAYER,
    CONF_PROVIDERS,
    CONF_ROUTES,
    CONF_SEARCH_ENABLED,
    CONF_USE_GOOGLE_SEARCH_TOOL,
    DEFAULT_AI_TASK_NAME,
    DEFAULT_AUDIO_OUTPUT,
    DEFAULT_SEARCH_ENABLED,
    DEFAULT_STT_NAME,
    DEFAULT_TITLE,
    DEFAULT_TTS_NAME,
    DOMAIN,
    LOGGER,
    RECOMMENDED_AI_TASK_OPTIONS,
    RECOMMENDED_CHAT_MODEL,
    RECOMMENDED_STT_OPTIONS,
    RECOMMENDED_TTS_OPTIONS,
    SERVICE_INTERRUPT_EXTERNAL_AUDIO,
    SERVICE_GENERATE_LATENCY_PHRASES,
    SERVICE_PREVIEW_LATENCY_PHRASE,
    TIMEOUT_MILLIS,
)
from .core import LunaCore
from .provider_hub.credentials import (
    credentials_from_entry,
    providers_from_entry,
    routes_from_entry,
)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS = (
    Platform.AI_TASK,
    Platform.CONVERSATION,
    Platform.STT,
    Platform.TTS,
)

type LunaAssistantConfigEntry = ConfigEntry[LunaCore]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Luna Assistant Prime."""

    await async_migrate_integration(hass)

    async def async_interrupt_external_audio(call: ServiceCall) -> None:
        """Stop every external player configured for Luna voice output."""
        targets: set[str] = set()
        for entry in hass.config_entries.async_entries(DOMAIN):
            for subentry in entry.subentries.values():
                if subentry.subentry_type != "conversation":
                    continue
                if (
                    subentry.data.get(CONF_AUDIO_OUTPUT, DEFAULT_AUDIO_OUTPUT)
                    == AUDIO_OUTPUT_ATOM
                ):
                    continue
                entity_id = subentry.data.get(CONF_OUTPUT_MEDIA_PLAYER)
                if isinstance(entity_id, str) and entity_id:
                    targets.add(entity_id)

        if not targets:
            LOGGER.debug("Barge-in requested without a configured external player")
            return

        await hass.services.async_call(
            "media_player",
            "media_stop",
            {},
            target={"entity_id": sorted(targets)},
            blocking=True,
        )
        LOGGER.info(
            "Barge-in stopped Luna external audio on: %s",
            ", ".join(sorted(targets)),
        )

    if not hass.services.has_service(DOMAIN, SERVICE_INTERRUPT_EXTERNAL_AUDIO):
        hass.services.async_register(
            DOMAIN,
            SERVICE_INTERRUPT_EXTERNAL_AUDIO,
            async_interrupt_external_audio,
        )

    async def async_generate_latency_phrases(call: ServiceCall) -> None:
        """Generate missing or stale latency feedback files."""
        for entry in hass.config_entries.async_entries(DOMAIN):
            if entry.runtime_data is not None:
                await entry.runtime_data.feedback.async_generate()

    async def async_preview_latency_phrase(call: ServiceCall) -> None:
        """Preview one generated phrase on a selected media player."""
        phrase = str(call.data.get("phrase", "")).strip()
        media_player = str(call.data.get("media_player", "")).strip()
        for entry in hass.config_entries.async_entries(DOMAIN):
            if entry.runtime_data is not None:
                await entry.runtime_data.feedback.async_play_phrase(
                    phrase, media_player or None
                )

    if not hass.services.has_service(DOMAIN, SERVICE_GENERATE_LATENCY_PHRASES):
        hass.services.async_register(
            DOMAIN,
            SERVICE_GENERATE_LATENCY_PHRASES,
            async_generate_latency_phrases,
        )
    if not hass.services.has_service(DOMAIN, SERVICE_PREVIEW_LATENCY_PHRASE):
        hass.services.async_register(
            DOMAIN,
            SERVICE_PREVIEW_LATENCY_PHRASE,
            async_preview_latency_phrase,
        )

    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: LunaAssistantConfigEntry
) -> bool:
    """Set up Luna Assistant Prime from a config entry."""

    credentials = credentials_from_entry(entry)
    google_keys = [
        str(item.get("api_key", "")).strip()
        for item in credentials
        if item.get("provider") == "google"
        and item.get("enabled", True)
        and str(item.get("api_key", "")).strip()
    ]
    if not google_keys:
        raise ConfigEntryAuthFailed("No enabled Google credential is configured")

    failures: list[Exception] = []
    for google_key in google_keys:
        try:
            client = await hass.async_add_executor_job(
                partial(Client, api_key=google_key)
            )
            await client.aio.models.get(
                model=RECOMMENDED_CHAT_MODEL,
                config={"http_options": {"timeout": TIMEOUT_MILLIS}},
            )
            break
        except (APIError, Timeout) as err:
            failures.append(err)
    else:
        last_error = failures[-1]
        if all(
            isinstance(err, ClientError) and "API_KEY_INVALID" in str(err)
            for err in failures
        ):
            raise ConfigEntryAuthFailed(str(last_error)) from last_error
        if any(isinstance(err, Timeout) for err in failures):
            raise ConfigEntryNotReady(last_error) from last_error
        raise ConfigEntryError(last_error) from last_error

    entry.runtime_data = await LunaCore.async_create(hass, entry)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: LunaAssistantConfigEntry
) -> bool:
    """Unload Luna Assistant Prime."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.providers.async_close()
    return unloaded


async def async_update_options(
    hass: HomeAssistant, entry: LunaAssistantConfigEntry
) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_integration(hass: HomeAssistant) -> None:
    """Migrate integration entry structure."""

    # Make sure we get enabled config entries first
    entries = sorted(
        hass.config_entries.async_entries(DOMAIN),
        key=lambda e: e.disabled_by is not None,
    )
    if not any(entry.version == 1 for entry in entries):
        return

    api_keys_entries: dict[str, tuple[ConfigEntry, bool]] = {}
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    for entry in entries:
        use_existing = False
        subentry = ConfigSubentry(
            data=entry.options,
            subentry_type="conversation",
            title=entry.title,
            unique_id=None,
        )
        if entry.data[CONF_API_KEY] not in api_keys_entries:
            use_existing = True
            all_disabled = all(
                e.disabled_by is not None
                for e in entries
                if e.data[CONF_API_KEY] == entry.data[CONF_API_KEY]
            )
            api_keys_entries[entry.data[CONF_API_KEY]] = (entry, all_disabled)

        parent_entry, all_disabled = api_keys_entries[entry.data[CONF_API_KEY]]

        hass.config_entries.async_add_subentry(parent_entry, subentry)
        if use_existing:
            hass.config_entries.async_add_subentry(
                parent_entry,
                ConfigSubentry(
                    data=MappingProxyType(RECOMMENDED_TTS_OPTIONS),
                    subentry_type="tts",
                    title=DEFAULT_TTS_NAME,
                    unique_id=None,
                ),
            )
        conversation_entity_id = entity_registry.async_get_entity_id(
            "conversation",
            DOMAIN,
            entry.entry_id,
        )
        device = device_registry.async_get_device_by_identifier(
            (DOMAIN, entry.entry_id), entry.entry_id
        )

        if conversation_entity_id is not None:
            conversation_entity_entry = entity_registry.entities[conversation_entity_id]
            entity_disabled_by = conversation_entity_entry.disabled_by
            if (
                entity_disabled_by is er.RegistryEntryDisabler.CONFIG_ENTRY
                and not all_disabled
            ):
                # Device and entity registries will set the disabled_by flag to None
                # when moving a device or entity disabled by CONFIG_ENTRY to an enabled
                # config entry, but we want to set it to DEVICE or USER instead,
                entity_disabled_by = (
                    er.RegistryEntryDisabler.DEVICE
                    if device
                    else er.RegistryEntryDisabler.USER
                )
            entity_registry.async_update_entity(
                conversation_entity_id,
                config_entry_id=parent_entry.entry_id,
                config_subentry_id=subentry.subentry_id,
                disabled_by=entity_disabled_by,
                new_unique_id=subentry.subentry_id,
            )

        if device is not None:
            # Device and entity registries will set the disabled_by flag to None
            # when moving a device or entity disabled by CONFIG_ENTRY to an enabled
            # config entry, but we want to set it to USER instead,
            device_disabled_by: dr.DeviceEntryDisabler | UndefinedType = UNDEFINED
            if (
                device.disabled_by is dr.DeviceEntryDisabler.CONFIG_ENTRY
                and not all_disabled
            ):
                device_disabled_by = dr.DeviceEntryDisabler.USER
            device_registry.async_update_device(
                device.id,
                disabled_by=device_disabled_by,
                new_identifiers={(DOMAIN, subentry.subentry_id)},
                new_config_entry_id=parent_entry.entry_id,
                new_config_subentry_id=subentry.subentry_id,
            )

        if not use_existing:
            await hass.config_entries.async_remove(entry.entry_id)
        else:
            _add_ai_task_and_stt_subentries(hass, entry)
            hass.config_entries.async_update_entry(
                entry,
                title=DEFAULT_TITLE,
                options={},
                version=2,
                minor_version=4,
            )


async def async_migrate_entry(
    hass: HomeAssistant, entry: LunaAssistantConfigEntry
) -> bool:
    """Migrate entry."""
    LOGGER.debug("Migrating from version %s:%s", entry.version, entry.minor_version)

    if entry.version == 2 and entry.minor_version == 1:
        # Add TTS subentry which was missing in 2025.7.0b0
        if not any(
            subentry.subentry_type == "tts" for subentry in entry.subentries.values()
        ):
            hass.config_entries.async_add_subentry(
                entry,
                ConfigSubentry(
                    data=MappingProxyType(RECOMMENDED_TTS_OPTIONS),
                    subentry_type="tts",
                    title=DEFAULT_TTS_NAME,
                    unique_id=None,
                ),
            )

        # Devices left in both the config entry and its subentry by Home Assistant Core
        # 2025.7.0b0-2025.7.0b1 are collapsed onto the subentry by the device registry
        # migration, so there's nothing to correct here.
        hass.config_entries.async_update_entry(entry, minor_version=2)

    if entry.version == 2 and entry.minor_version == 2:
        _add_ai_task_and_stt_subentries(hass, entry)
        hass.config_entries.async_update_entry(entry, minor_version=3)

    if entry.version == 2 and entry.minor_version == 3:
        # Fix migration where the disabled_by flag was not set correctly.
        # We can currently only correct this for enabled config entries,
        # because migration does not run for disabled config entries. This
        # is asserted in tests, and if that behavior is changed, we should
        # correct also disabled config entries.
        device_registry = dr.async_get(hass)
        entity_registry = er.async_get(hass)
        devices = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
        entity_entries = er.async_entries_for_config_entry(
            entity_registry, entry.entry_id
        )
        if entry.disabled_by is None:
            # If the config entry is not disabled, we need to set the disabled_by
            # flag on devices to USER, and on entities to DEVICE, if they are set
            # to CONFIG_ENTRY.
            for device in devices:
                if device.disabled_by is not dr.DeviceEntryDisabler.CONFIG_ENTRY:
                    continue
                device_registry.async_update_device(
                    device.id,
                    disabled_by=dr.DeviceEntryDisabler.USER,
                )
            for entity in entity_entries:
                if entity.disabled_by is not er.RegistryEntryDisabler.CONFIG_ENTRY:
                    continue
                entity_registry.async_update_entity(
                    entity.entity_id,
                    disabled_by=er.RegistryEntryDisabler.DEVICE,
                )
        hass.config_entries.async_update_entry(entry, minor_version=4)

    if entry.version == 2 and entry.minor_version < 6:
        # Existing conversation subentries need no destructive migration:
        # missing audio-output fields safely default to Atom.
        hass.config_entries.async_update_entry(entry, minor_version=6)

    if entry.version == 2 and entry.minor_version < 7:
        # Prime v1 introduces provider-aware subentries. Existing subentries
        # remain Google-backed through the safe default and need no data rewrite.
        hass.config_entries.async_update_entry(
            entry,
            title=DEFAULT_TITLE,
            minor_version=7,
        )

    if entry.version == 2 and entry.minor_version < 8:
        # Prime v1.1 reads legacy Google/Azure keys into the central credential
        # catalogue. Legacy fields remain accepted for a non-destructive update.
        credentials = credentials_from_entry(entry)
        hass.config_entries.async_update_entry(
            entry,
            options={**entry.options, "credentials": credentials},
            minor_version=8,
        )

    if entry.version == 2 and entry.minor_version < 9:
        # Prime v1.1.1 exposes the existing central catalogue as independent
        # Google and Azure lists. Storage is already list-based; no rewrite is
        # required, so every configured credential and usage id is preserved.
        hass.config_entries.async_update_entry(entry, minor_version=9)

    if entry.version == 2 and entry.minor_version < 10:
        # Prime v1.2 merges legacy instances by technology, preserves every
        # credential id, and introduces ordered routes for five capabilities.
        migrated_options = dict(entry.options)
        migrated_options[CONF_PROVIDERS] = providers_from_entry(entry)
        migrated_options[CONF_ROUTES] = routes_from_entry(entry)
        if CONF_SEARCH_ENABLED not in migrated_options:
            legacy_search_values = [
                bool(subentry.data[CONF_USE_GOOGLE_SEARCH_TOOL])
                for subentry in entry.subentries.values()
                if subentry.subentry_type == "conversation"
                and CONF_USE_GOOGLE_SEARCH_TOOL in subentry.data
            ]
            migrated_options[CONF_SEARCH_ENABLED] = (
                any(legacy_search_values)
                if legacy_search_values
                else DEFAULT_SEARCH_ENABLED
            )
        migrated_options.pop("provider_instances", None)
        migrated_options.pop("provider_limits", None)
        migrated_options.pop("credentials", None)
        hass.config_entries.async_update_entry(
            entry,
            options=migrated_options,
            minor_version=10,
        )

    LOGGER.debug(
        "Migration to version %s:%s successful", entry.version, entry.minor_version
    )

    return True


def _add_ai_task_and_stt_subentries(
    hass: HomeAssistant, entry: LunaAssistantConfigEntry
) -> None:
    """Add AI Task and STT subentries to the config entry."""
    hass.config_entries.async_add_subentry(
        entry,
        ConfigSubentry(
            data=MappingProxyType(RECOMMENDED_AI_TASK_OPTIONS),
            subentry_type="ai_task_data",
            title=DEFAULT_AI_TASK_NAME,
            unique_id=None,
        ),
    )
    hass.config_entries.async_add_subentry(
        entry,
        ConfigSubentry(
            data=MappingProxyType(RECOMMENDED_STT_OPTIONS),
            subentry_type="stt",
            title=DEFAULT_STT_NAME,
            unique_id=None,
        ),
    )
