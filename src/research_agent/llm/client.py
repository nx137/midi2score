"""OpenAI-compatible HTTP client used by the optional LLM adapter."""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


class LLMError(RuntimeError):
    """Raised when the optional LLM provider cannot satisfy a request."""


@dataclass(frozen=True)
class DeepSeekConfig:
    model: str
    base_url: str
    api_key: str
    timeout_seconds: float = 120.0
    max_tokens: int = 4096
    temperature: float = 0.0
    system_prompt: str = "你是 PedNotate 科研控制平面的规划顾问。只提出计划，不执行命令，不修改权限。"
    reasoning_effort: str = ""
    disable_response_storage: bool = False
    extra_body: dict[str, Any] = field(default_factory=dict)
    log_dir: str = ""


class DeepSeekClient:
    """Small provider-agnostic client for DeepSeek/OpenAI-compatible endpoints."""

    def __init__(self, config: DeepSeekConfig, opener: Callable[..., Any] | None = None) -> None:
        if not config.model:
            raise LLMError("MIDI2SCORE_LLM_MODEL is required")
        if not config.base_url:
            raise LLMError("MIDI2SCORE_LLM_BASE_URL is required")
        if not config.api_key:
            raise LLMError("DEEPSEEK_API_KEY or MIDI2SCORE_LLM_API_KEY is required")
        self.config = config
        self._opener = opener or urllib.request.urlopen

    def _endpoint(self) -> str:
        base = self.config.base_url.rstrip("/")
        if base.endswith("/chat/completions"):
            return base
        return base + "/chat/completions"

    def complete(self, prompt: str) -> str:
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": self.config.system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "stream": False,
        }
        if self.config.reasoning_effort:
            payload["reasoning_effort"] = self.config.reasoning_effort
        if self.config.disable_response_storage:
            payload["store"] = False
        for key, value in self.config.extra_body.items():
            if key not in {"model", "messages", "stream"}:
                payload[key] = value
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            self._endpoint(),
            data=data,
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        started = time.time()
        try:
            with self._opener(request, timeout=self.config.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1000]
            raise LLMError(f"LLM HTTP {exc.code}: {detail}") from exc
        except Exception as exc:
            raise LLMError(f"LLM request failed: {type(exc).__name__}: {exc}") from exc
        try:
            body = json.loads(raw)
            content = body["choices"][0]["message"]["content"]
        except Exception as exc:
            raise LLMError(f"LLM response schema error: {raw[:500]}") from exc
        self._log(prompt, str(content), time.time() - started)
        return str(content)

    def _log(self, prompt: str, content: str, elapsed: float) -> None:
        if not self.config.log_dir:
            return
        log_dir = Path(self.config.log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        record = {
            "provider": "deepseek",
            "model": self.config.model,
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "response_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            "elapsed_seconds": round(elapsed, 6),
        }
        (log_dir / "llm_calls.jsonl").open("a", encoding="utf-8").write(json.dumps(record, ensure_ascii=False) + "\n")


__all__ = ["DeepSeekConfig", "DeepSeekClient", "LLMError"]
