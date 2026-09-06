# Phase 1.5 MLX Storage Adapter

## Status

Phase 1.5 connects StateBraid's backend-neutral compute-continuity policy to a real MLX-LM prompt-cache storage object without letting StateBraid reach into MLX-LM private trie/LRU internals.

The integration is **storage-ready, not production-default-enabled**. It proves the adapter and transactional storage contract against the real MLX cache object; switching a production server to StateBraid policy remains an explicit later activation step.

## Companion MLX capability

The reviewed local MLX-LM companion commit is:

- `2e1279055c68f14ac53e75131e7e34d5b9e0b042`
- `feat(cache): expose external-policy storage facade`

That commit remains local in the research MLX-LM repository. It is not vendored into StateBraid and was not pushed as part of Phase 1.5.

The companion exposes one narrow public capability:

```text
prompt_cache.transactional_storage()
    -> capture(model, tokens)
    -> remove(model, tokens)
    -> restore(model, tokens, snapshot)
    -> insert(model, tokens, payload, cache_type=...)
```

The facade owns all access to MLX-LM's internal prompt trie, LRU bookkeeping, and byte counters. StateBraid only sees opaque entry snapshots.

## Exclusive policy ownership

The transactional facade deliberately bypasses MLX-LM native:

- capacity eviction;
- native LRU choice;
- prefix deduplication/pruning.

This is required because StateBraid already made those mechanical decisions before mutation. Allowing the native cache to perform an additional, independent eviction pass would create two policy authorities and could make StateBraid metadata diverge from real KV residency.

Therefore a cache object using this facade must have **one mutation owner**: `CacheCoordinator`.

Native `insert_cache()` behavior remains unchanged when the facade is not used.

`CognitivePromptCache` explicitly rejects the external-policy facade. It already owns separate pin/stable/active policy metadata, so layering StateBraid on the same object would create split-brain policy. A future StateBraid-enabled MLX server should use the plain MLX prompt-cache storage plus StateBraid policy, rather than stacking StateBraid above CognitivePromptCache.

## StateBraid side

`statebraid.adapters.mlx.MLXPromptCacheBackend` implements the Phase 1 `TransactionalBackend` contract by calling only the public transactional storage facade.

It does not access or name:

- `_trie`;
- `_lru`;
- `_n_bytes`;
- `_n_bytes_by_type`;
- CognitivePromptCache metadata.

StateBraid still has no import-time MLX dependency. The storage adapter is duck-typed against the public capability, while generation-safety integration dynamically imports MLX-LM only when invoked.

## Verified behavior

### StateBraid without MLX installed

- a clean `--no-local` clone of the committed feature branch passes the standard-library unittest suite;
- `pip install --no-deps --no-build-isolation --target ... .` succeeds from that clean clone and the package imports from outside the repository;
- real-MLX tests skip cleanly;
- Pyright remains 0 errors / 0 warnings / 0 informations;
- import/compile succeeds with no MLX package installed.

### Real MLX prompt-cache object

Using the MLX-LM companion worktree and its existing MLX virtual environment, Phase 1.5 verifies:

1. **External capacity ownership** — StateBraid can preserve two planned stable/active entries on a real `LRUPromptCache(max_size=1, max_bytes=1)`, proving native capacity policy is not silently re-running.
2. **Transactional rollback** — an injected successor insert failure restores both the exact previous MLX cache entry and the previous StateBraid policy state.
3. **Concurrent coordinator safety** — two threads mutating a real MLX storage object through one coordinator remain byte/entry-count consistent.
4. **Generation-safe exact hit** — an exact hit on the real MLX cache recovers the `N-1` checkpoint and replays the final token for a non-trimmable cache.
5. **Prefix removal correctness** — removing a shorter exact entry preserves a longer descendant and supports exact restore.

No model weights are required for these storage invariants, so Phase 1.5 does not load another large model merely to repeat behavior already exercised on the real cache implementation.

## Verification boundary

The MLX-LM committed baseline used for the companion branch was `3ed985a239e244377237495d490d81f8f5a96ad2`.

MLX relevant behavior after the companion patch:

- external storage facade tests: 5/5;
- existing CognitivePromptCache tests: 18/18;
- existing exact-cache generation tests: 9/9;
- total: **32/32 PASS**.

The MLX cache files have existing Pyright debt. A clean detached `3ed985a` A/B produced the same `94 errors / 2 warnings` before and after the companion patch, with no diagnostics in the newly added facade lines. StateBraid itself remains strictly Pyright-clean.

A second disposable compatibility worktree overlaid the companion commit with the current dirty research `cognitive_cache.py`, `server.py`, launcher, and current boundary/budget tests. After reproducing the original launcher environment shape, that current-state overlay passed **50/50** relevant tests. The overlay was deleted afterward; the original dirty MLX-LM main worktree was not modified.

## Not included

Phase 1.5 does not:

- turn StateBraid on by default inside the MLX-LM HTTP server;
- modify model loading or generation scheduling;
- change KV quantization defaults;
- add selected-evidence continuity;
- add S1/checkpoint producer logic;
- add provider-interruption recovery;
- upload the research MLX-LM companion branch.
