# Phase 1 Compute-Continuity Extraction

## Status

Phase 1 extracts the mature compute-continuity behavior from the research MLX-LM thin fork into a backend-neutral StateBraid core.

It is an extraction of **runtime policy and invariants**, not a copy of the MLX-LM fork.

## Reviewed source baseline

The reviewed research source state was:

- repository HEAD: `3ed985a239e244377237495d490d81f8f5a96ad2`;
- `cognitive_cache.py` SHA-256: `7d1fc2c4c091c493d53a7f144e30f017d45dafaca8dc258f2d8048703f1ec383`;
- `mlx_lm/server.py` SHA-256: `6004091883a6654eb94ecba41acc61b474a259397774154d6795d79d121b1bb9`.

The source working tree contained reviewed compute-continuity changes on top of that HEAD. The relevant source behavior was re-verified before extraction:

- cognitive-cache behavior: **18/18 PASS**;
- cache-boundary / rollback behavior: **11/11 PASS**;
- exact-cache generation safety: **9/9 PASS**.

Total source comparison baseline: **38/38 PASS**.

## Extracted invariants

### 1. Stable + active working set

StateBraid preserves distinct transient roles:

- `stable`: a cross-session reusable prefix admitted by mechanical reuse facts;
- `active`: a generation-safe current tail or successor.

The stable lane rotates independently. Active successors compact only an exact active predecessor that is a strict token prefix in the same namespace. Divergent active branches are not treated as the same lineage.

### 2. Sequence and byte budgets

Sequence capacity and byte capacity are independent hard constraints.

Pinned entries cannot consume every sequence slot: the default policy reserves transient capacity. Under byte pressure, a stable + active pair is protected when that pair itself fits the requested limit; older non-working entries may yield first.

If even the working pair cannot fit, hard capacity wins.

### 3. Stable admission uses observed reuse, not task semantics

Automatic stable replacement never reads prompt text or task meaning.

The policy uses only mechanical facts:

- whether the stable lane is empty;
- exact token-prefix identity;
- token length during cold bootstrap;
- actual reuse-hit count;
- repeated candidate observations without an intervening incumbent hit.

The runtime does not classify which task or agent is "important".

### 4. Transactional mutation

Policy planning is separated from backend KV storage mutation.

`CacheCoordinator` serializes the high-level operation:

1. plan admission / trim;
2. capture opaque backend references for affected keys;
3. mutate backend storage;
4. commit policy metadata only after backend success;
5. on failure, restore policy metadata and the captured backend references.

Backend payloads and namespace/model keys are never deep-copied by StateBraid.

### 5. Generation-safe exact hits

An exact prompt-cache hit may leave zero input tokens for the next generation step.

StateBraid therefore preserves the verified rule:

- trimmable cache: drop one cached token and replay the final prompt token;
- non-trimmable / hybrid cache: use the best `N-1` checkpoint and replay the final token;
- if no shorter checkpoint exists: recompute the full prompt rather than send an empty generation segment.

## Backend boundary

The core package does **not** import MLX or MLX-LM.

`statebraid.cache` owns:

- cache identity and exact token lineage;
- role/rank policy;
- stable admission probation;
- sequence/byte planning;
- trim planning;
- transaction orchestration;
- generation-safety decision logic.

`statebraid.adapters.mlx` is intentionally thin and imports MLX-LM only when called. At Phase 1 it contains the generation-safe exact-hit bridge.

The MLX-LM trie, KV tensor types, server request loop, cache serialization, quantization path, and launcher remain backend implementation details and are **not** copied into StateBraid core.

## Explicitly not included in Phase 1

- selected-evidence continuity;
- working-state / S1 checkpoint producer;
- provider `length` interruption resume;
- semantic evidence ranking;
- model weights or local model paths;
- benchmark result data or production logs;
- distributed KV tiers;
- KV quantization defaults;
- a full MLX storage adapter that reaches into private MLX-LM trie internals.

The last item is deliberate: StateBraid should first define a narrow adapter contract instead of depending on one fork's private cache data structures.

## StateBraid verification

Phase 1 deterministic verification currently covers:

- pin saturation and transient reserve;
- stable lane rotation;
- active exact-lineage compaction;
- byte-pressure working-pair protection;
- reuse-based stable probation;
- oversized-candidate fail-closed behavior;
- admission rollback;
- trim rollback;
- no-deepcopy opaque namespace handling;
- concurrent coordinator serialization;
- trimmable and non-trimmable exact-hit generation safety;
- `N-1` hybrid checkpoint boundary.

See `tests/test_cache_policy.py` and `tests/test_generation_safety.py`.
