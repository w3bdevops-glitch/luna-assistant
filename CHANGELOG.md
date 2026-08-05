# Changelog

## 0.3.1

- Hotfix: align `google-genai` with Home Assistant Core 2026.7.4 (`1.59.0`).
- Prevents the custom integration from upgrading the shared Python package to 2.16.0 and breaking the official Google Gemini integration.

## 0.3.0

- Added conversation personality presets.
- Added response-length presets.
- Added latency profiles: Fast, Balanced and Quality.
- Added voice mood presets.
- Added speaking pace presets.
- Presets are combined with the editable custom prompts.
- Kept all v0.2 model selectors and advanced parameters.

## 0.2.0

- Model selectors are visible by default for Conversation, STT and TTS.
- Added explicit defaults for all three model services.
- Added editable TTS voice-style instructions.
- Added a concise, natural Brazilian Portuguese Luna conversation prompt.
- Added a Brazilian Portuguese STT correction prompt.
