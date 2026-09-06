# StateBraid Architecture

## Layer model

StateBraid sits between an agent harness and a model-serving backend, but it owns
only the compute-continuity layer.

```text
Agent harness / coding agent / tool loop
  task + evidence + execution continuity
                |
                | serving requests
                v
        StateBraid Runtime
        compute continuity only
        - exact token/namespace identity
        - stable prefix
        - active lineage
        - sequence + byte budgets
        - transactional cache mutation
        - generation-safe reuse
        - factual telemetry
                |
                v
      model-serving backend (MLX first)
```

The initial implementation target is Apple Silicon / MLX because that is where
the research evidence exists. The architecture does not make MLX a permanent
semantic dependency, and it does not make any particular agent harness a
StateBraid dependency.

## Compute-continuity state

A minimal useful cache working set contains two transient roles:

- **stable**: a cross-session reusable prefix whose value has been established
  mechanically by real reuse;
- **active**: the current generation-safe successor/tail.

Pinned long-lived entries must not starve all transient capacity. Byte pressure
and sequence pressure are separate constraints and must both be enforced.

Cache mutation is transactional from the runtime's perspective: failed admission
must not silently corrupt bookkeeping or evict the previous valid working set.

## Identity and lineage

A cache identity is the exact token sequence inside an explicit namespace/trust
domain. Prefix hits are credited to the actual served prefix. Active-successor
compaction is allowed only for exact predecessor lineage.

StateBraid does not derive cache value from task text, tool semantics, evidence
meaning, or legacy agent labels such as `goal`, `rules`, `evidence`, or
`identity`.

## Agent-state boundary

StateBraid intentionally does **not** own task/evidence/execution continuity.
Selected raw evidence, receipt folding, working-state/checkpoints, provider
interruption recovery, durable session/event state, Goal/handoff, SubAgent
ownership, and ExecutionWorkspace state belong to the agent harness.

This separation is important because cache value and task/evidence value are
different questions. StateBraid answers only the mechanical cache question:
which exact compute state can be reused safely under resource constraints?

## Serving and telemetry boundary

The runtime may expose factual compute telemetry such as:

- cache mode;
- matched/cached token counts when actually known;
- stable/active sequence counts;
- cache bytes;
- admission/eviction counters;
- exact-hit replay facts.

The harness may record those facts, but StateBraid does not turn them into task
strategy, fold decisions, evidence selection, stopping decisions, or tool policy.

## Integration qualification contract

StateBraid integration benchmarks may observe agent-level outcomes such as task
completion, tool-call count, canonical duplicate calls, evidence checks, and
truncation. Those metrics are **external regression signals**: they detect whether
a compute-layer change accidentally altered the agent's observable behavior.
They do not make StateBraid the owner of those semantics.

Compute-facing benchmark metrics should report at least:

- prompt/input tokens;
- cached tokens only when provider telemetry is actually present;
- new-prefill tokens only when cached-token telemetry is known;
- stable/active residency and bytes when exposed;
- request latency;
- TTFT only when it is truly measured, never inferred from full request latency;
- worker health/fatal conditions.

## Phase 1 implementation boundary

The first product extraction deliberately separates policy from storage:

- `statebraid.cache.policy` owns cache roles, exact token lineage, capacity
  planning, stable admission, active-successor compaction, trim planning, and
  transactional orchestration.
- `statebraid.cache.generation` owns backend-neutral exact-hit generation safety.
- `statebraid.adapters.mlx` is a thin optional integration layer and has no
  import-time MLX dependency.

The core does not embed an MLX-LM trie or copy KV tensors. Backend snapshots are
opaque references, so transaction rollback restores references rather than cloning
model state. Concurrent runtimes should use `CacheCoordinator` high-level methods
so planning, backend mutation, and policy commit remain one serialized operation.

See [`PHASE1_COMPUTE_CONTINUITY.md`](PHASE1_COMPUTE_CONTINUITY.md) for source
provenance and the reviewed extraction boundary.

## Phase 1.5 MLX storage boundary

The MLX adapter depends on one public capability, `transactional_storage()`, not
MLX-LM private cache fields. The facade exposes exact capture/remove/restore/insert
and is an exclusive-storage mode: StateBraid owns admission and eviction while it
is active.

`CognitivePromptCache` is intentionally not stackable with StateBraid policy
because both would own stable/active admission. Production activation must select
one cache-policy authority.

See [`PHASE1_5_MLX_STORAGE_ADAPTER.md`](PHASE1_5_MLX_STORAGE_ADAPTER.md).

## Compute Contract v0.1

Phase C freezes the compute-visible behavior and minimum public subset described in
[`COMPUTE_FREEZE_V0_1.md`](COMPUTE_FREEZE_V0_1.md). Internal implementation may
evolve while that contract remains satisfied. Contract-breaking changes require a
new contract version and requalification.
