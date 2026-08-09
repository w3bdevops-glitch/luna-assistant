"""Static regression checks for pre-generated Search latency feedback."""

from pathlib import Path

ROOT = Path(__file__).parents[1] / "custom_components" / "luna_assistant"
FEEDBACK = (ROOT / "latency_feedback.py").read_text(encoding="utf-8")
CONST = (ROOT / "const.py").read_text(encoding="utf-8")
SERVICES = (ROOT / "services.yaml").read_text(encoding="utf-8")

for phrase in (
    "Hum… deixa eu pesquisar isso.",
    "Estou verificando para você.",
    "Só um instante, vou consultar informações atualizadas.",
    "Deixa eu confirmar essa informação.",
    "Um momento, estou pesquisando.",
):
    assert phrase in CONST

assert "async_prepare_defaults" in FEEDBACK
assert "async_generate" in FEEDBACK
assert "_config_hash" in FEEDBACK
assert "SystemRandom().shuffle" in FEEDBACK
assert "async_mask_latency" in FEEDBACK
assert "media-source://media_source/local/" in FEEDBACK
assert "generate_latency_phrases" in SERVICES
assert "preview_latency_phrase" in SERVICES

print("Luna latency-feedback validation passed.")
