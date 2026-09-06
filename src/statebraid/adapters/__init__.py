"""Optional backend adapters for StateBraid."""

from .mlx import MLXPromptCacheBackend, generation_safe_prompt_cache_hit

__all__ = ["MLXPromptCacheBackend", "generation_safe_prompt_cache_hit"]
