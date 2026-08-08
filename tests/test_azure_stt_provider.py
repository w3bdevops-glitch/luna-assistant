"""Static validation for Azure short-audio STT."""

from pathlib import Path

ROOT = Path(__file__).parents[1] / "custom_components" / "luna_assistant"
AZURE = (ROOT / "provider_hub/azure.py").read_text(encoding="utf-8")
HUB = (ROOT / "provider_hub/hub.py").read_text(encoding="utf-8")
STT = (ROOT / "stt.py").read_text(encoding="utf-8")
CONFIG = (ROOT / "config_flow.py").read_text(encoding="utf-8")

assert "ProviderCapability.STT" in AZURE
assert ".stt.speech.microsoft.com/" in AZURE
assert "speech/recognition/conversation/cognitiveservices/v1" in AZURE
assert "audio/wav; codecs=audio/pcm; samplerate=16000" in AZURE
assert "audio/ogg; codecs=opus" in AZURE
assert "RecognitionStatus" in AZURE
assert "async def async_transcribe" in AZURE
assert "adapter.async_transcribe" in HUB
assert 'language=metadata.language or "pt-BR"' in STT
assert "CONF_AZURE_STT_PROFANITY" in CONFIG

print("Luna Azure STT adapter validation passed.")
