"""Environment-based construction of the optional LLM adapter."""

from __future__ import annotations

import os
from collections.abc import Mapping

from .client import DeepSeekClient, DeepSeekConfig, LLMError

DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_SYSTEM_PROMPT = (
    "你是 PedNotate 科研控制平面的规划顾问。"
    "只能提出计划、候选命令和不确定性；不得声称执行已完成，"
    "不得修改目标、权限、训练顺序、主指标或 TASK_CHARTER.md。"
)


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def build_llm_from_env(env: Mapping[str, str] | None = None):
    """Return a callable for planning, or None when LLM is disabled.

    Enabling the provider without complete configuration is a hard configuration error.
    """
    values = os.environ if env is None else env
    if not _truthy(values.get("MIDI2SCORE_LLM_ENABLED")):
        return None
    provider = values.get("MIDI2SCORE_LLM_PROVIDER", "deepseek").strip().lower()
    if provider not in {"deepseek", "openai_compatible"}:
        raise LLMError(f"unsupported MIDI2SCORE_LLM_PROVIDER: {provider}")
    model = values.get("MIDI2SCORE_LLM_MODEL", "").strip()
    base_url = values.get("MIDI2SCORE_LLM_BASE_URL", DEFAULT_BASE_URL).strip()
    api_key = values.get("MIDI2SCORE_LLM_API_KEY") or values.get("DEEPSEEK_API_KEY") or ""
    if not model:
        raise LLMError("MIDI2SCORE_LLM_MODEL is required when LLM is enabled")
    if not api_key:
        raise LLMError("DEEPSEEK_API_KEY or MIDI2SCORE_LLM_API_KEY is required when LLM is enabled")
    config = DeepSeekConfig(
        model=model,
        base_url=base_url,
        api_key=api_key,
        timeout_seconds=float(values.get("MIDI2SCORE_LLM_TIMEOUT_SECONDS", "120")),
        max_tokens=int(values.get("MIDI2SCORE_LLM_MAX_TOKENS", "4096")),
        temperature=float(values.get("MIDI2SCORE_LLM_TEMPERATURE", "0")),
        system_prompt=values.get("MIDI2SCORE_LLM_SYSTEM_PROMPT", DEFAULT_SYSTEM_PROMPT),
        log_dir=values.get("MIDI2SCORE_LLM_LOG_DIR", ""),
    )
    client = DeepSeekClient(config)
    return client.complete


__all__ = ["build_llm_from_env", "DEFAULT_BASE_URL", "DEFAULT_SYSTEM_PROMPT"]
