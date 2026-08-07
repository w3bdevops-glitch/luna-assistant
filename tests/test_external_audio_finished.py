"""Static validation for external playback completion notification."""

from pathlib import Path

SOURCE = (Path(__file__).parents[1] / "custom_components/luna_assistant/conversation.py").read_text()

assert "_async_notify_satellites_when_external_audio_finishes" in SOURCE
assert 'current in ("playing", "buffering")' in SOURCE
assert 'current in ("idle", "off", "paused")' in SOURCE
assert '_luna_external_audio_finished' in SOURCE

print("Luna external audio completion validation passed.")
