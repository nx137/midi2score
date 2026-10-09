from __future__ import annotations

import json
from pathlib import Path

import pytest

from research_agent.llm.client import DeepSeekClient, DeepSeekConfig, LLMError
from research_agent.llm.factory import build_llm_from_env


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_llm_disabled_by_default():
    assert build_llm_from_env({}) is None


def test_llm_fails_closed_when_enabled_without_model_or_key():
    with pytest.raises(LLMError):
        build_llm_from_env({"MIDI2SCORE_LLM_ENABLED": "true"})
    with pytest.raises(LLMError):
        build_llm_from_env({"MIDI2SCORE_LLM_ENABLED": "true", "MIDI2SCORE_LLM_MODEL": "model-x"})


def test_deepseek_client_parses_openai_compatible_response(tmp_path):
    calls = []

    def opener(request, timeout):
        calls.append((request, timeout))
        return FakeResponse({"choices": [{"message": {"content": "OK"}}]})

    config = DeepSeekConfig(
        model="deepseek-flash",
        base_url="https://api.example.test",
        api_key="secret",
        reasoning_effort="high",
        disable_response_storage=True,
        extra_body={"thinking": {"type": "enabled"}},
        log_dir=str(tmp_path / "logs"),
    )
    client = DeepSeekClient(config, opener=opener)
    assert client.complete("hello") == "OK"
    request, timeout = calls[0]
    body = json.loads(request.data.decode("utf-8"))
    assert request.full_url == "https://api.example.test/chat/completions"
    assert request.headers["Authorization"] == "Bearer secret"
    assert body["reasoning_effort"] == "high"
    assert body["store"] is False
    assert body["thinking"] == {"type": "enabled"}
    log_text = (tmp_path / "logs" / "llm_calls.jsonl").read_text(encoding="utf-8")
    assert "secret" not in log_text
    assert "prompt_sha256" in log_text
    assert "response_sha256" in log_text
