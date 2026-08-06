# Luna Assistant

## Current version: 0.3.1

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


## What is new in 0.2.0

Open the Luna Assistant integration, choose the service and use its
**Configure** action. Disable/enable recommended settings as needed and select
the Gemini model from the list returned by your Google account.

The Luna TTS service now has an editable **Voice style instructions** field.
The default asks for a cheerful, welcoming, natural Brazilian Portuguese
delivery. This instruction is sent to Gemini TTS together with the response.

Existing 0.1.0 entries may keep their saved settings. Reconfigure each Luna
sub-service, or remove and add the Luna integration again, to apply all new
defaults.


## What is new in 0.3.0

Luna Conversation now exposes:

- Personality: Playful, Warm, Direct, Teacher or Technical
- Response length: Very short, Short, Balanced or Detailed
- Latency profile: Fast, Balanced or Quality

Luna TTS now exposes:

- Voice mood: Cheerful, Warm, Calm, Enthusiastic or Professional
- Speaking pace: Slow, Natural or Fast

These presets are combined with the editable prompt fields, so advanced
users keep full control while everyday adjustments become much easier.


## 0.3.1 compatibility hotfix

Home Assistant Core 2026.7.4 pins `google-genai==1.59.0`. Luna Assistant
now uses the same version to avoid a shared dependency conflict with the
official Google Gemini integration.


## Saída de áudio externa

Edite a subentrada **Luna Conversation** e escolha:

- Saída de áudio: Atom ou media player externo
- Media player externo
- Volume
- Usar como anúncio
- Fallback para o Atom

Com saída externa, a resposta é enviada por `tts.speak` ao player selecionado
e removida da resposta do satélite para evitar áudio duplicado.

O firmware Luna Satellite v0.2.0-alpha envia `esphome.luna_barge_in` quando
detecta nova fala. A integração usa esse evento para parar o player externo.
