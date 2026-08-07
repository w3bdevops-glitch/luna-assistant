"""Static validation for Luna Satellite wake-word barge-in."""

from pathlib import Path


SOURCE = (Path(__file__).parents[2] / "upload/luna-satellite.yaml").read_text(
    encoding="utf-8"
)

wake_index = SOURCE.index("on_wake_word_detected:")
action_index = SOURCE.index(
    "action: luna_assistant.interrupt_external_audio", wake_index
)
stop_index = SOURCE.index("- voice_assistant.stop:", action_index)
start_index = SOURCE.index("- voice_assistant.start:", stop_index)

assert wake_index < action_index < stop_index < start_index
assert 'firmware_version: "0.1.5-stable"' in SOURCE
assert "homeassistant.action:" in SOURCE
assert "on_error:" in SOURCE[action_index:start_index]
assert "not:\n                  voice_assistant.is_running:" in SOURCE

print("Luna Satellite barge-in validation passed.")
