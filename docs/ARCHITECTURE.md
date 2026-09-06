# StateBraid Architecture

## Layer model

StateBraid sits between an agent harness and a model-serving backend.

```text
Agent harness / coding agent / tool loop
                |
                v
        StateBraid Runtime
        |                  |
        |                  +-- continuity projection
        |                      selected raw evidence
        |                      recoverable receipts
        |                      interrupted partial state
        |
        +-- serving continuity
            stable prefix
            active tail
            cache budget / admission
            generation-safe reuse
                |
                v
      model serving backend (MLX first)
```

The initial implementation target is Apple Silicon / MLX because that is where the research evidence exists. The architecture should not make MLX a permanent semantic dependency.

## Compute-continuity state

A minimal useful cache working set contains two transient roles:

- **stable**: a cross-session reusable prefix whose value has been established mechanically by real reuse;
- **active**: the current generation-safe successor/tail.

Pinned long-lived entries must not starve all transient capacity. Byte pressure and sequence pressure are separate constraints and must both be enforced.

Cache mutation should be transactional from the runtime's perspective: failed admission must not silently corrupt bookkeeping or evict the previous valid working set.

## Evidence-continuity state

Evidence selection operates on complete tool-protocol groups. The runtime can assign short fold-local IDs but persisted identity must use stable mechanical digests.

Selected groups remain original messages. The runtime does not replace selected raw evidence with an assistant-authored summary and claim equivalence.

Working-state text, when supplied by the model, is opaque to the runtime except for mechanical size/scope validation.

## Cache value vs evidence value

These are intentionally different concepts:

- cache protection asks which prefix is valuable to avoid recomputation;
- evidence selection asks which direct observations the model says remain necessary for reasoning.

Neither is allowed to stand in for the other. If both apply, the runtime must combine them mechanically and surface budget pressure instead of inventing a semantic pruning policy.

## Interruption state

Normal completion and provider interruption are separate state transitions.

A truncated assistant message must retain enough metadata to distinguish it from a completed answer. Continuation should be one-shot and factual: the runtime exposes that the prior model output was interrupted and preserves the exact partial content.

## Benchmark contract

StateBraid benchmarks should report at least:

- task completion / truncation;
- tool-call count;
- duplicate tool-call count;
- tool errors;
- evidence claims and direct observed support;
- prompt tokens;
- cached tokens only when provider telemetry is actually present;
- new-prefill tokens only when cached-token telemetry is known;
- per-round request latency;
- TTFT only when it is truly measured, never inferred from full request latency.

## Phase 1 implementation boundary

The first product extraction deliberately separates policy from storage:

- `statebraid.cache.policy` owns cache roles, exact token lineage, capacity planning, stable admission, active-successor compaction, trim planning, and transactional orchestration.
- `statebraid.cache.generation` owns backend-neutral exact-hit generation safety.
- `statebraid.adapters.mlx` is a thin optional integration layer and has no import-time MLX dependency.

The core does not embed an MLX-LM trie or copy KV tensors. Backend snapshots are opaque references, so transaction rollback restores references rather than cloning model state. Concurrent runtimes should use `CacheCoordinator` high-level methods so planning, backend mutation, and policy commit remain one serialized operation.

See [`PHASE1_COMPUTE_CONTINUITY.md`](PHASE1_COMPUTE_CONTINUITY.md) for source provenance and the reviewed extraction boundary.
