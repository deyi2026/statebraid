# StateBraid Compute Contract v0.1

## Status

**Frozen after Phase 1.6.2 real-integration qualification.**

The v0.1 compute contract is the smallest StateBraid surface that an agent
harness or model-serving adapter may rely on without inheriting StateBraid's
internal implementation details.

The machine-readable contract marker is:

```python
from statebraid import COMPUTE_CONTRACT_VERSION

assert COMPUTE_CONTRACT_VERSION == "0.1"
```

Freeze does not mean the implementation can never change. It means compatible
additions and internal refactors are allowed, while removal or behavior changes
to the contract below require explicit compatibility handling and qualification.

## Qualification baseline

The freeze is based on StateBraid commit `2c469844108b8fc29ef436592301bc1d3b3a5380`
and the Phase 1.6.2 qualification recorded in
`PHASE1_6_2_REAL_INTEGRATION_QUALIFICATION.md`.

That qualification used an immutable LFL source snapshot and demonstrated that
the Cognitive control and StateBraid candidate were identical for completion,
evidence checks, tool traces, token accounting, cache-hit accounting and
new-prefill accounting. A real StateBraid exact-repeat canary also verified the
generation-safe N-1 replay path after semantic-tag hardening.

## Frozen public entry points

The following names are the minimum supported public subset. New names may be
added without changing the contract version; these names must not silently
disappear or change incompatible calling semantics within contract v0.1.

### `statebraid.cache`

- `CacheKey`
- `matched_prefix_key`
- `WorkingSetPolicy`
- `CacheCoordinator`
- `AdmissionPlan`
- `TrimPlan`
- `ensure_generation_safe_exact_hit`
- `is_generation_safe_hybrid_checkpoint`

### `statebraid.adapters`

- `MLXPromptCacheBackend`
- `MLXStateBraidPromptCache`
- `generation_safe_prompt_cache_hit`

The MLX adapter remains optional. Importing `statebraid.cache` must not require
MLX to be installed.

## Frozen behavior invariants

### 1. Exact mechanical cache identity

Cache identity is the exact pair of backend namespace and exact token sequence.
StateBraid does not infer cache identity from task names, message meanings,
human-readable text or semantic similarity.

Actual reuse credit is assigned to the prefix the backend really served, using
the observed remainder, rather than to the full requested prompt.

### 2. Semantic-blind default policy

The default `WorkingSetPolicy` has no semantic pin roles. Labels such as
`goal`, `rules`, `evidence` and `identity` have no built-in residency or rank
authority.

An operator may explicitly configure mechanical `pin_roles`, but that is an
opt-in backend/operator contract and is not inferred from agent meaning.

### 3. Stable and active working set

- `stable` represents a mechanically reusable shared prefix;
- `active` represents the current successor/tail;
- an active predecessor is compacted only when the successor has exact token
  prefix lineage in the same namespace;
- a fitting stable + active pair is protected under ordinary pressure;
- hard sequence or byte limits ultimately win when the pair itself cannot fit.

Stable promotion remains based on mechanical reuse observations, not semantic
importance.

### 4. Independent sequence and byte budgets

Sequence capacity and byte capacity are separate hard resource constraints.
Increasing one must not silently disable the other.

Transient reserve prevents configured pins from consuming every cache slot.

### 5. Transactional mutation and rollback

`CacheCoordinator` owns the serialized plan -> backend mutation -> policy commit
boundary for normal integrations. Backend failure must restore both StateBraid
policy state and the affected opaque backend references.

StateBraid must not deep-copy backend KV payloads merely to provide rollback.

### 6. Generation-safe exact hits

An exact cache hit must never send an empty generation input to the model.

- trimmable cache may replay the final token after trimming one cached token;
- non-trimmable/hybrid cache uses an exact N-1 checkpoint when available;
- if a safe shorter cache is unavailable, the full prompt is recomputed.

For the currently reference-qualified `Ornith-1.5-35B-A3B-MLX` Qwen3.6-derived
hybrid/non-trimmable path, N-1 replay is the verified real-model behavior. This is
not a support claim for all Qwen-derived models.

### 7. Single cache-policy authority

StateBraid and another admission/eviction policy must not simultaneously own the
same prompt-cache working set. The MLX activation remains explicit and
default-off, while CognitivePromptCache remains available as rollback/control.

The runtime-qualified scope is still the exact hybrid/non-trimmable reference
profile in [`SUPPORTED_SCOPE_V0_1.md`](SUPPORTED_SCOPE_V0_1.md). Generic
trimmable-KV production parity is not implied by this freeze.

### 8. Factual telemetry only

Cache telemetry may report mechanical facts such as mode, sequence count, byte
count, evictions, promotions, rejections and cache hits. Telemetry does not give
StateBraid authority to decide task completion, evidence importance, tool
selection, folding strategy or retry strategy.

Existing telemetry keys may be extended additively. Removing or changing the
meaning of a key already consumed by an integration requires compatibility
review.

## Change classes and required gates

### Class A -- compatible additive/internal change

Examples:

- additive telemetry;
- a new backend adapter;
- internal performance refactoring with unchanged observable behavior;
- additional tests or documentation.

Required gates:

1. full zero-dependency StateBraid unit suite;
2. Pyright 0/0/0;
3. compile and `git diff/show --check`;
4. fresh-checkout install/import;
5. privacy and scope review.

### Class B -- compute-path implementation change

Examples:

- changes to admission/eviction planning;
- stable promotion or active-lineage implementation;
- backend transaction/capture/restore behavior;
- generation-safe exact-hit implementation;
- MLX storage integration.

In addition to Class A, require the relevant backend parity suite and real
generation canary. If the change can affect harness-visible cache behavior,
repeat the frozen LFL A/B qualification before merging.

Class B is acceptable under contract v0.1 only when contract-visible behavior
remains compatible.

### Class C -- contract-breaking change

Examples:

- semantic ranking or semantic pinning becoming a StateBraid default;
- changing exact token/namespace cache identity;
- weakening independent hard budgets;
- removing transactional rollback;
- permitting empty-input exact generation hits;
- changing stable/active lineage semantics incompatibly;
- removing a frozen public entry point;
- making StateBraid activation implicitly coexist with another policy authority.

Class C requires a new compute contract version, explicit migration notes and a
new real-integration qualification. It must not be smuggled in as a bug fix.

## Explicitly outside this compute contract

This freeze does not assign StateBraid ownership of agent semantics. In
particular, the compute contract does not include:

- selected raw evidence or evidence importance;
- working-state/checkpoint meaning;
- provider-interruption task continuation policy;
- Goal/handoff ownership;
- SubAgent ownership;
- ExecutionWorkspace state;
- task completion, tool choice, quality judgment or semantic retry policy.

Those boundaries belong to an agent harness such as LFL or to the model. The
Phase D product-boundary cleanup will make that separation explicit across the
broader StateBraid documentation; Phase C freezes only the compute layer.
