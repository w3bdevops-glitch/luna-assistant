"""Regression tests for Luna web-search configuration."""

from pathlib import Path


ROOT = Path(__file__).parents[1] / "custom_components" / "luna_assistant"


def test_search_is_not_disabled_by_fast_profile() -> None:
    """Fast mode must still expose Google Search when enabled."""
    source = (ROOT / "entity.py").read_text(encoding="utf-8")

    assert "options.get(CONF_USE_GOOGLE_SEARCH_TOOL) is True" in source
    assert "Google Search disabled for this request by Fast" not in source


def test_search_and_home_assistant_api_are_not_mutually_exclusive() -> None:
    """The options flow must accept Search and HA function tools together."""
    source = (ROOT / "config_flow.py").read_text(encoding="utf-8")

    assert "invalid_google_search_option" not in source


def test_search_is_enabled_for_new_conversations() -> None:
    """Recommended conversation settings should opt into selective search."""
    source = (ROOT / "const.py").read_text(encoding="utf-8")

    assert "RECOMMENDED_USE_GOOGLE_SEARCH_TOOL = True" in source
    assert "CONF_USE_GOOGLE_SEARCH_TOOL: RECOMMENDED_USE_GOOGLE_SEARCH_TOOL" in source
