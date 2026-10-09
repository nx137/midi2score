import pytest


@pytest.fixture(autouse=True)
def disable_real_llm_for_unit_tests(monkeypatch):
    """Keep the normal test suite offline and deterministic."""
    monkeypatch.setenv("MIDI2SCORE_LLM_ENABLED", "false")
