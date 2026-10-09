"""Environment-based construction of the optional LLM adapter."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from .client import DeepSeekClient, DeepSeekConfig, LLMError

DEFAULT_BASE_URL = "https://api.deepseek.com"
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_LOCAL_CONFIG = REPO_ROOT / "config" / "llm.local.env"
PLACEHOLDER_KEYS = {"", "REPLACE_WITH_YOUR_KEY", "YOUR_API_KEY"}
DEFAULT_SYSTEM_PROMPT = (
    "你是 PedNotate 科研控制平面的规划顾问。"
    "只能提出计划、候选命令和不确定性；不得声称执行已完成，"
    "不得修改目标、权限、训练顺序、主指标或 TASK_CHARTER.md。"
)


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def load_env_file(path: Path | str) -> dict[str, str]:
    """Read a small KEY=VALUE file; it is a convenience, not a secret store."""
    p = Path(path)
    if not p.exists():
        return {}
    values: dict[str, str] = {}
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"')
    return values


def _runtime_env() -> dict[str, str]:
    config_path = os.environ.get("MIDI2SCORE_LLM_CONFIG_FILE", str(DEFAULT_LOCAL_CONFIG))
    values = load_env_file(config_path)
    values.update(os.environ)
    return values


def build_llm_from_env(env: Mapping[str, str] | None = None):
    """Return a callable for planning, or None when LLM is disabled.

    Enabling the provider without complete configuration is a hard configuration error.
    """
    runtime_mode = env is None
    values = _runtime_env() if runtime_mode else env
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
    if not api_key.strip():
        raise LLMError("DEEPSEEK_API_KEY or MIDI2SCORE_LLM_API_KEY is required when LLM is enabled")
    if runtime_mode and api_key.strip() in PLACEHOLDER_KEYS:
        return None
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


__all__ = ["build_llm_from_env", "load_env_file", "DEFAULT_BASE_URL", "DEFAULT_LOCAL_CONFIG", "DEFAULT_SYSTEM_PROMPT"]
