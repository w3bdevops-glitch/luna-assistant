# Luna Assistant

Custom Home Assistant integration derived from the official Google Gemini
integration.

## v0.1.0

- Conversation agent
- Speech-to-text
- Text-to-speech
- AI task entity
- HACS-compatible repository structure
- Independent domain: `luna_assistant`
- Default TTS model changed to `gemini-2.5-flash-preview-tts`
- Model selection remains available through the service reconfiguration flow

## Install from GitHub

1. Upload this repository's files to the root of
   `w3bdevops-glitch/luna-assistant`.
2. Create a GitHub release tagged `v0.1.0`.
3. In HACS, add the repository as a custom repository of category
   **Integration**.
4. Install **Luna Assistant** and restart Home Assistant.
5. Go to **Settings → Devices & services → Add integration** and search for
   **Luna Assistant**.
6. Enter your Google AI Studio API key.

## Important

This is an experimental derivative integration. Keep the official Google
Gemini integration installed until Luna Assistant is tested successfully.

## Source

Derived from Home Assistant Core's
`google_generative_ai_conversation` integration under Apache-2.0.
