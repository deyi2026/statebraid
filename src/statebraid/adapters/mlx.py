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
from statebraid.cache.policy import (
    CacheCoordinator,
    CacheKey,
    WorkingSetPolicy,
    matched_prefix_key,
)


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


def _prompt_cache_nbytes(payload: object) -> int:
    """Return the mechanical byte size of one MLX prompt-cache payload."""
    try:
        return sum(max(0, int(getattr(item, "nbytes"))) for item in cast(Any, payload))
    except (TypeError, ValueError, AttributeError) as exc:
        raise TypeError("MLX prompt-cache payload must expose per-entry nbytes") from exc


class MLXStateBraidPromptCache:
    """MLX prompt-cache facade with StateBraid as the sole policy authority.

    Reads are delegated to the backend's ordinary nearest-prefix lookup. Exact
    storage mutation goes through ``transactional_storage()`` so StateBraid never
    reaches into MLX-LM private trie/LRU fields. Agent-level labels such as
    ``goal``, ``rules`` or ``evidence`` carry no built-in pin authority; default
    residency is decided only from token identity, observed reuse, lineage and
    resource limits.
    """

    statebraid_policy_active = True

    def __init__(
        self,
        prompt_cache: Any,
        *,
        max_sequences: int,
        max_bytes: int,
        transient_reserve: int | None = None,
    ) -> None:
        self._prompt_cache = prompt_cache
        self.max_size = max(0, int(max_sequences))
        self.max_bytes = max(0, int(max_bytes))
        self.policy = WorkingSetPolicy(
            max_sequences=self.max_size,
            max_bytes=self.max_bytes,
            transient_reserve=transient_reserve,
        )
        self.backend = MLXPromptCacheBackend(prompt_cache)
        self.coordinator = CacheCoordinator(self.policy, self.backend)

    def __len__(self) -> int:
        return self.policy.n_sequences

    @property
    def nbytes(self) -> int:
        return self.policy.nbytes

    def fetch_nearest_cache(self, model: Any, tokens: list[int]):
        cache, rest = self._prompt_cache.fetch_nearest_cache(model, tokens)
        matched = matched_prefix_key(model, tokens, rest)
        if cache is not None and matched is not None:
            self.coordinator.observe_hit(matched)
        return cache, rest

    def insert_cache(
        self,
        model: Any,
        tokens: list[int],
        prompt_cache: object,
        *,
        cache_type: str = "assistant",
    ) -> bool:
        key = CacheKey.from_tokens(model, tokens)
        return self.coordinator.admit_entry(
            key,
            prompt_cache,
            role=cache_type,
            nbytes=_prompt_cache_nbytes(prompt_cache),
        )

    def insert_stable_candidate(
        self, model: Any, tokens: list[int], prompt_cache: object
    ) -> bool:
        key = CacheKey.from_tokens(model, tokens)
        return self.coordinator.admit_stable_candidate(
            key,
            prompt_cache,
            nbytes=_prompt_cache_nbytes(prompt_cache),
        )

    def insert_active_successor(
        self,
        model: Any,
        tokens: list[int],
        prompt_cache: object,
        *,
        predecessor_tokens: Sequence[int],
    ) -> bool:
        key = CacheKey.from_tokens(model, tokens)
        predecessor = CacheKey.from_tokens(model, predecessor_tokens)
        return self.coordinator.admit_entry(
            key,
            prompt_cache,
            role="active",
            nbytes=_prompt_cache_nbytes(prompt_cache),
            predecessor=predecessor,
        )

    def trim_to(
        self, *, n_sequences: int | None = None, n_bytes: int | None = None
    ) -> bool:
        return self.coordinator.trim_to(n_sequences=n_sequences, n_bytes=n_bytes)

    def stats_by_type(self) -> dict[str, dict[str, int]]:
        snapshot = self.policy.capture_state()
        result: dict[str, dict[str, int]] = {}
        for entry in snapshot.entries.values():
            stats = result.setdefault(entry.role, {"n_sequences": 0, "n_bytes": 0})
            stats["n_sequences"] += 1
            stats["n_bytes"] += entry.nbytes
        return result

    def activation_stats(self) -> dict[str, int | str]:
        snapshot = self.policy.capture_state()
        return {
            "mode": "statebraid",
            "n_sequences": len(snapshot.entries),
            "n_bytes": snapshot.nbytes,
            "pin_evictions": snapshot.pin_evictions,
            "pin_quota_evictions": snapshot.pin_quota_evictions,
            "active_successor_evictions": snapshot.active_successor_evictions,
            "stable_candidate_promotions": snapshot.stable_candidate_promotions,
            "stable_candidate_rejections": snapshot.stable_candidate_rejections,
        }


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
