"""Static validation for Luna's external wake-word playback guard."""

from __future__ import annotations

from pathlib import Path

SOURCE_PATH = (
    Path(__file__).parents[1]
    / "custom_components"
    / "luna_assistant"
    / "conversation.py"
)
SOURCE = SOURCE_PATH.read_text(encoding="utf-8")

service_index = SOURCE.index("if await self._async_route_with_luna_tts")
clear_index = SOURCE.index("result.response.speech.clear()", service_index)
log_index = SOURCE.index('"enabled; total %.0f ms"', clear_index)

assert service_index < clear_index < log_index
assert "_ExternalPlaybackTracker" not in SOURCE
assert "async_wait_for_completion" not in SOURCE
assert "return immediately" in SOURCE
assert "re-enables only its local micro wake word" in SOURCE
assert "target_entity_id = media_player_state.entity_id" in SOURCE
assert "friendly_name" not in SOURCE

print("Luna external wake-word playback guard validation passed.")
