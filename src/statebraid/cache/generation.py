"""Generation-safety helpers independent of a concrete inference backend."""
from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TypeVar

CacheT = TypeVar("CacheT")
TokenT = TypeVar("TokenT")


def ensure_generation_safe_exact_hit(
    cache: CacheT | None,
    rest: Sequence[TokenT],
    prompt: Sequence[TokenT],
    *,
    can_trim: Callable[[CacheT], bool],
    trim_one: Callable[[CacheT], None],
    fetch_shorter: Callable[[Sequence[TokenT]], tuple[CacheT | None, Sequence[TokenT]]],
) -> tuple[CacheT | None, list[TokenT]]:
    """Guarantee that generation receives at least one input token.

    Exact prompt-cache hits may return an empty remainder. Trimmable KV can drop
    one cached token and replay it. Non-trimmable/hybrid state must use the best
    cache for ``prompt[:-1]`` or recompute the full prompt when none exists.
    """
    rest_list = list(rest)
    prompt_list = list(prompt)
    if cache is None or rest_list or not prompt_list:
        return cache, rest_list
    if can_trim(cache):
        trim_one(cache)
        return cache, prompt_list[-1:]

    prefix_cache, prefix_rest = fetch_shorter(prompt_list[:-1])
    if prefix_cache is None:
        return None, prompt_list
    return prefix_cache, list(prefix_rest) + prompt_list[-1:]


def is_generation_safe_hybrid_checkpoint(cache_tokens: Sequence[object], prompt: Sequence[object]) -> bool:
    """A hybrid checkpoint is generation-safe only at the exact N-1 prefix."""
    return len(cache_tokens) + 1 == len(prompt)
