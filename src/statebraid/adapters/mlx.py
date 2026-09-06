"""Thin MLX-LM adapter hooks.

StateBraid has no import-time dependency on MLX. Generation helpers import
MLX-LM only when called; storage integration depends only on a narrow public
``transactional_storage()`` capability exposed by the backend object.
"""
from __future__ import annotations

import importlib
from collections.abc import Sequence
from typing import Any, Protocol, cast

from statebraid.cache.generation import ensure_generation_safe_exact_hit
from statebraid.cache.policy import CacheKey


class _MLXTransactionalStorage(Protocol):
    def capture(self, model: Any, tokens: list[int]) -> Any: ...
    def restore(self, model: Any, tokens: list[int], snapshot: Any) -> None: ...
    def remove(self, model: Any, tokens: list[int]) -> Any: ...
    def insert(
        self, model: Any, tokens: list[int], payload: object, *, cache_type: str
    ) -> None: ...


class MLXPromptCacheBackend:
    """Adapt an MLX-LM prompt cache to StateBraid's transactional backend.

    The prompt-cache object must expose ``transactional_storage()``. StateBraid
    never reads MLX-LM's trie, LRU queues, byte counters, or other private state.
    The returned storage facade is expected to be exclusively managed by the
    StateBraid coordinator while active.
    """

    def __init__(self, prompt_cache: Any):
        factory = getattr(prompt_cache, "transactional_storage", None)
        if factory is None or not callable(factory):
            raise TypeError(
                "MLX prompt cache lacks transactional_storage() capability"
            )
        self._storage = cast(_MLXTransactionalStorage, factory())
        for name in ("capture", "restore", "remove", "insert"):
            method = getattr(self._storage, name, None)
            if method is None or not callable(method):
                raise TypeError(f"MLX transactional storage lacks {name}()")

    def capture(self, key: CacheKey) -> Any:
        return self._storage.capture(key.namespace, list(key.tokens))

    def restore(self, key: CacheKey, snapshot: Any) -> None:
        self._storage.restore(key.namespace, list(key.tokens), snapshot)

    def remove(self, key: CacheKey) -> None:
        self._storage.remove(key.namespace, list(key.tokens))

    def insert(self, key: CacheKey, payload: object, *, role: str) -> None:
        self._storage.insert(
            key.namespace,
            list(key.tokens),
            payload,
            cache_type=role,
        )


def generation_safe_prompt_cache_hit(
    prompt_cache: Any,
    model_key: Any,
    prompt: list[int],
    cache: Any,
    rest: list[int],
):
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
