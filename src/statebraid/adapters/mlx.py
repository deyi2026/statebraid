"""Thin MLX-LM adapter hooks.

The StateBraid core has no import-time dependency on MLX.  This adapter imports
MLX-LM only when its wrapper is called.
"""
from __future__ import annotations

import importlib
from collections.abc import Sequence
from typing import Any

from statebraid.cache.generation import ensure_generation_safe_exact_hit


def generation_safe_prompt_cache_hit(prompt_cache: Any, model_key: Any, prompt: list[int], cache: Any, rest: list[int]):
    """Apply StateBraid exact-hit generation safety to an MLX-LM prompt cache."""
    cache_module = importlib.import_module("mlx_lm.models.cache")
    can_trim_prompt_cache = cache_module.can_trim_prompt_cache
    trim_prompt_cache = cache_module.trim_prompt_cache

    def trim_one(value: Any) -> None:
        trim_prompt_cache(value, 1)

    def fetch_shorter(tokens: Sequence[int]) -> tuple[Any | None, Sequence[int]]:
        return prompt_cache.fetch_nearest_cache(model_key, list(tokens))

    return ensure_generation_safe_exact_hit(
        cache,
        rest,
        prompt,
        can_trim=can_trim_prompt_cache,
        trim_one=trim_one,
        fetch_shorter=fetch_shorter,
    )
