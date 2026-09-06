# StateBraid v0.1 Product Boundary

## Product statement

StateBraid is an agent-aware local inference runtime that preserves both compute continuity and task-state continuity during long-running agent work.

The v0.1 boundary exists to prevent the research project from becoming an unbounded collection of serving, memory, planning, and agent features.

## The three v0.1 capabilities

### 1. Compute continuity

StateBraid may manage mechanical serving state such as:

- prompt/KV cache entries;
- stable shared prefixes;
- active session tails;
- sequence-slot and byte budgets;
- cache admission, eviction, and recovery bookkeeping.

It must preserve correctness before hit rate. Cross-session reuse must never permit state from one ownership domain to be interpreted as another session's content.

### 2. Selected-evidence continuity

When old tool work must be folded, StateBraid may expose mechanically identified evidence groups and let the model select which original groups remain direct.

A valid selected group is atomic:

- original assistant tool declaration;
- all matching tool-result messages required by the protocol group.

The runtime may validate identity, completeness, size, scope, and recoverability. It must not infer relevance, sufficiency, task completion, or semantic importance on the model's behalf.

Unselected evidence may be projected as a recoverable receipt when durable recovery exists.

### 3. Provider-interruption continuity

A provider finish reason such as `length` or `max_tokens` is an interruption boundary, not a normal completion boundary.

StateBraid should retain the exact partial assistant output and expose only factual runtime state needed for a later continuation. It must not rewrite durable human input to manufacture a continuation instruction.

## Ownership boundary

### Runtime owns

- cache correctness;
- protocol integrity;
- immutable identifiers and digests;
- byte/token/resource limits;
- provider finish-state facts;
- storage and recovery mechanics;
- authorization/security hard boundaries.

### Model owns

- what evidence is relevant;
- whether evidence is sufficient;
- task strategy;
- tool choice;
- whether to continue or answer;
- semantic checkpoint contents when a checkpoint capability is available.

## Explicitly dormant in v0.1 baseline

Automatic checkpoint production is not a required enabled feature for the v0.1 baseline. Research showed that exposing a checkpoint capability can be made non-coercive, but current model adoption is not yet strong enough to justify enabling a producer by default.

## Success criteria

A v0.1 candidate should demonstrate all of the following on repeatable agent benchmarks:

1. warm stable-prefix reuse without cross-session contamination;
2. bounded cache residency under both sequence and byte pressure;
3. generation-safe cache hits;
4. selected raw evidence produces no more semantic re-checks than full raw history on validated tasks;
5. selected evidence materially reduces provider-visible context compared with full raw history;
6. provider-length interruption resumes from the actual partial rather than restarting the answer;
7. benchmark reports distinguish cache-reported tokens from unknown cache telemetry;
8. duplicate tool calls, evidence support, completion, truncation, and new-prefill tokens are measured separately.
