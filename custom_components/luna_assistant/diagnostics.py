# Modified for Luna Assistant.
# Derived from Home Assistant Core's Google Gemini integration,
# licensed under the Apache License 2.0.

"""Diagnostics support for Luna Assistant Prime."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from .const import CONF_AZURE_SPEECH_KEY

TO_REDACT = {CONF_API_KEY, CONF_AZURE_SPEECH_KEY}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return async_redact_data(
        {
            "title": entry.title,
            "data": entry.data,
            "options": entry.options,
            "subentries": {
                subentry_id: {
                    "type": subentry.subentry_type,
                    "title": subentry.title,
                    "data": subentry.data,
                }
                for subentry_id, subentry in entry.subentries.items()
            },
            "prime": entry.runtime_data.diagnostics(),
        },
        TO_REDACT,
    )
