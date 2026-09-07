"""Optional backend adapters for StateBraid."""

from .mlx import (
    MLX_BACKEND_DESCRIPTOR,
    MLXPromptCacheBackend,
    MLXStateBraidPromptCache,
    generation_safe_prompt_cache_hit,
)

__all__ = [
    "MLX_BACKEND_DESCRIPTOR",
    "MLXPromptCacheBackend",
    "MLXStateBraidPromptCache",
    "generation_safe_prompt_cache_hit",
]
