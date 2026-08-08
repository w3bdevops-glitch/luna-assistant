"""Static regression checks for Luna's global reliability policy."""

import ast

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONST_SOURCE = (ROOT / "custom_components/luna_assistant/const.py").read_text()
CONVERSATION_SOURCE = (
    ROOT / "custom_components/luna_assistant/conversation.py"
).read_text()


def test_reliability_policy_is_global() -> None:
    """The mandatory policy must be included in every effective prompt."""
    assert "RELIABILITY_PROMPT" in CONST_SOURCE
    assert "RELIABILITY_PROMPT," in CONVERSATION_SOURCE
    assert CONVERSATION_SOURCE.index("RELIABILITY_PROMPT,") < (
        CONVERSATION_SOURCE.index("PERSONALITY_PROMPTS.get(personality)")
)


def _reliability_prompt_value() -> str:
    """Read the constant without importing Home Assistant dependencies."""
    module = ast.parse(CONST_SOURCE)
    for node in module.body:
        if (
            isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "RELIABILITY_PROMPT"
                for target in node.targets
            )
        ):
            return ast.literal_eval(node.value)
    raise AssertionError("RELIABILITY_PROMPT was not found")


def test_reliability_policy_covers_failure_modes() -> None:
    """The policy must prohibit invention and define uncertainty fallbacks."""
    prompt = _reliability_prompt_value()
    required_phrases = (
        "Nunca invente",
        "use a pesquisa na internet antes de responder",
        "Não sei responder com segurança",
        "Não consegui confirmar essa informação agora",
        "nunca afirme que pesquisou quando não pesquisou",
    )
    for phrase in required_phrases:
        assert phrase in prompt
