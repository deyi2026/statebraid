"""Optional backend adapters for StateBraid."""

from .mlx import (
    MLXPromptCacheBackend,
    MLXStateBraidPromptCache,
    generation_safe_prompt_cache_hit,
)

__all__ = [
    "MLXPromptCacheBackend",
    "MLXStateBraidPromptCache",
    "generation_safe_prompt_cache_hit",
]
