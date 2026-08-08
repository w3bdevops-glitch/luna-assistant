"""Static validation for the first non-Google provider adapter."""

from pathlib import Path


ROOT = Path(__file__).parents[1] / "custom_components" / "luna_assistant"
AZURE = (ROOT / "provider_hub/azure.py").read_text(encoding="utf-8")
CONFIG = (ROOT / "config_flow.py").read_text(encoding="utf-8")
DIAGNOSTICS = (ROOT / "diagnostics.py").read_text(encoding="utf-8")

assert ".tts.speech.microsoft.com/" in AZURE
assert "cognitiveservices/v1" in AZURE
assert '"Ocp-Apim-Subscription-Key"' in AZURE
assert '"X-Microsoft-OutputFormat"' in AZURE
assert "application/ssml+xml" in AZURE
assert "validate_wav(audio)" in AZURE
assert "CONF_AZURE_SPEECH_KEY" in CONFIG
assert "TextSelectorType.PASSWORD" in CONFIG
assert "CONF_AZURE_SPEECH_KEY" in DIAGNOSTICS

print("Luna Azure TTS adapter validation passed.")
