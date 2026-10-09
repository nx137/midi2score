"""Optional provider adapters for the research control plane."""

from .factory import build_llm_from_env

__all__ = ["build_llm_from_env"]
