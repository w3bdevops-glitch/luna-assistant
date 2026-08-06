"""Standalone validation of Luna audio helpers."""

from __future__ import annotations

import importlib.util
import io
import math
from pathlib import Path
import struct
import sys
import types
import wave


class HomeAssistantError(Exception):
    pass


def load_helpers():
    ha = types.ModuleType("homeassistant")
    exceptions = types.ModuleType("homeassistant.exceptions")
    exceptions.HomeAssistantError = HomeAssistantError
    sys.modules["homeassistant"] = ha
    sys.modules["homeassistant.exceptions"] = exceptions

    package = types.ModuleType("luna_assistant")
    package.__path__ = []
    sys.modules["luna_assistant"] = package

    const = types.ModuleType("luna_assistant.const")
    import logging
    const.LOGGER = logging.getLogger("luna_assistant")
    sys.modules["luna_assistant.const"] = const

    path = (
        Path(__file__).parents[1]
        / "custom_components"
        / "luna_assistant"
        / "helpers.py"
    )
    spec = importlib.util.spec_from_file_location("luna_assistant.helpers", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["luna_assistant.helpers"] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def pcm(duration=0.20, rate=24000):
    frames = int(duration * rate)
    return b"".join(
        struct.pack("<h", int(7000 * math.sin(2 * math.pi * 440 * i / rate)))
        for i in range(frames)
    )


helpers = load_helpers()
raw = pcm()
wav_data = helpers.convert_to_wav(
    raw, "audio/l16; rate=24000; channels=1"
)
info = helpers.validate_wav(wav_data)
assert wav_data[:4] == b"RIFF"
assert wav_data[8:12] == b"WAVE"
assert info.sample_rate == 24000
assert info.channels == 1
assert info.bits_per_sample == 16
assert info.frame_count == len(raw) // 2
assert helpers.convert_to_wav(wav_data, "audio/wav") == wav_data

try:
    helpers.convert_to_wav(b"\x00", "audio/l16;rate=24000")
except HomeAssistantError:
    pass
else:
    raise AssertionError("Misaligned PCM must be rejected")

print("Luna Assistant audio validation passed.")
