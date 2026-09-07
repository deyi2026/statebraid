# StateBraid

**Agent-aware compute-continuity runtime for long-running local agents.**

StateBraid is built around one practical goal:

> Less recompute. Less redo.

The source tree is currently at **`0.1.0rc1` release-candidate metadata**. This is
not yet a formal public `v0.1.0` release: the final release-readiness audit and tag
gate remain separate steps.

StateBraid directly owns the **less recompute** half of that promise. It preserves
mechanical serving state so long-running agents do not repeatedly rebuild the same
model prefix. The **less redo** half is an integration outcome: task, evidence and
execution continuity remain the responsibility of the agent harness and the model,
not a second semantic decision system inside StateBraid.

## v0.1 product boundary

StateBraid v0.1 is intentionally a **compute-continuity runtime**. Its supported
surface is:

- exact cache identity from namespace + token sequence;
- mechanically established stable-prefix reuse;
- exact active-successor lineage;
- bounded KV/prompt-cache residency under independent sequence and byte limits;
- transactional cache mutation and rollback;
- generation-safe exact-hit reuse, including the validated N-1 hybrid path;
- factual cache telemetry for integration and qualification;
- a narrow MLX adapter as the first backend integration.

StateBraid does not decide which evidence matters, whether a task is complete, or
how an interrupted agent run should continue. Semantic labels from an agent harness
such as `goal`, `rules`, `evidence`, or `identity` do not gain default cache
priority or pin authority.

## Responsibility boundary

**StateBraid owns compute continuity:** token identity, cache residency, stable and
active lineage, resource budgets, transactional storage mutation, generation-safe
reuse, and factual compute telemetry.

**The agent harness owns task/evidence/execution continuity:** selected raw evidence,
fold/receipt mechanics, working-state/checkpoint storage, provider-interruption
recovery, durable session/event state, Goal/handoff state, SubAgent ownership, and
ExecutionWorkspace state.

**The model owns semantic judgment:** what matters, what evidence is sufficient,
which tool to use, what to preserve when the harness exposes that capability, and
whether to continue or answer.

StateBraid and an agent harness should integrate through a narrow serving/API
boundary rather than share a second semantic control plane.

## Non-goals for v0.1

StateBraid v0.1 is **not**:

- a general distributed inference platform competing with vLLM or SGLang;
- an autonomous task planner;
- an evidence selector, fold engine, semantic memory ranker, or checkpoint producer;
- a provider-interruption/task-resume controller;
- a Goal/handoff, SubAgent, ExecutionWorkspace, or durable session manager;
- a hidden-chain-of-thought persistence system;
- a replacement for the agent harness or tool layer.

## v0.1 supported runtime scope

The backend-neutral compute contract is broader than the current **runtime
qualification**. The v0.1 reference-qualified serving profile is intentionally
narrow:

- Apple Silicon / macOS;
- the packaged reference patch against exact upstream `mlx-lm` base
  `6d21ce4b065a2e163fa6de76a9936c61aeb5784a`;
- `Ornith-1.5-35B-A3B-MLX`, a Qwen3.6-derived hybrid/non-trimmable cache path;
- MLX batch generation, model-native thinking, unquantized KV;
- prompt concurrency `1`, decode concurrency `1`;
- prompt-cache profile of 8 sequences / 4 GiB in the end-to-end qualification;
- explicit StateBraid activation, which remains **default-off**.

This is **not** a blanket support claim for Qwen models, all MLX models, arbitrary
MLX-LM commits, generic trimmable KV, quantized KV, draft/speculative decoding,
distributed serving, non-batch generation, or higher server concurrency.

Single-user `local-default` cache isolation is qualified. Multiple trust domains
are qualified as a **cache-isolation primitive only** and require a trusted
authenticated gateway/harness to derive `cache_namespace`; StateBraid is not the
authentication or TLS boundary.

See [`docs/SUPPORTED_SCOPE_V0_1.md`](docs/SUPPORTED_SCOPE_V0_1.md), or query the
installed package directly:

```bash
statebraid-doctor scope --json
```

## v0.1 reference distribution path

StateBraid is an independent Python package; it does not vendor the research
MLX-LM fork. The first backend distribution is a version-bound reference patch
against clean upstream `ml-explore/mlx-lm` commit
`6d21ce4b065a2e163fa6de76a9936c61aeb5784a`.

Install StateBraid from the current checkout or a built wheel, then export its
packaged reference integration:

```bash
python -m pip install .
statebraid-reference mlx --output statebraid-mlx.patch
```

Apply that patch only to the exact qualified MLX-LM base, make the patched MLX
package importable in the server environment, and require the compatibility gate
before activation:

```bash
statebraid-doctor mlx
```

StateBraid activation remains explicit and default-off:

```bash
MLX_LM_STATEBRAID=1 python -m mlx_lm.server --model <model> ...
```

Rollback is mechanical: stop the server, unset `MLX_LM_STATEBRAID`, and restart
the patched backend on its native `LRUPromptCache` path. A request may provide
`cache_namespace`; multi-tenant callers must have a trusted authenticated layer
derive that value rather than accepting an arbitrary tenant name from an
untrusted client.

See [`docs/DISTRIBUTION_BOUNDARY.md`](docs/DISTRIBUTION_BOUNDARY.md) for the exact
patch SHA256, compatibility API markers, apply procedure, and security boundary.

## Current status

Phase 1 extracted compute continuity into a backend-neutral core. The repository
contains stable/active working-set policy, sequence + byte budget planning,
transactional backend coordination, and exact-hit generation safety without
importing the MLX-LM fork into the core package.

Phase 1.5 adds a narrow MLX storage adapter backed by a public transactional-storage
capability. StateBraid does not access MLX-LM private trie/LRU fields.

Phase 1.6 validates that adapter in a real MLX server behind an explicit opt-in
activation. The canary preserves a single cache-policy authority, rejects
StateBraid + CognitivePromptCache coexistence, and keeps the normal server path
unchanged by default. The successful canary does **not** make StateBraid the
default production cache policy.

Phase 1.6.1 removes legacy semantic cache authority from the StateBraid path.
Phase 1.6.2 then qualifies the hardened mechanical policy through an unchanged,
immutable LFL snapshot: task/evidence/tool behavior and cache/new-prefill accounting
match the Cognitive control, real exact-hit N-1 replay remains generation-safe,
and the prior Cognitive runtime is restored after testing. Those task/evidence
metrics are **integration regression signals**, not StateBraid-owned semantics.

Phase C freezes that qualified compute surface as **Compute Contract v0.1**. The
freeze protects a minimum public API subset and black-box behavior invariants while
still allowing compatible additions and internal optimization. Changes to cache
identity, semantic blindness, stable/active lineage, hard budgets, transactional
rollback, generation-safe exact hits, or required public entry points must follow
the compatibility gates in
[`docs/COMPUTE_FREEZE_V0_1.md`](docs/COMPUTE_FREEZE_V0_1.md).

Phase D aligns the product definition with that frozen compute contract: StateBraid
is no longer described as the owner of selected-evidence, interruption recovery,
or other agent-layer continuity mechanisms.

The real model qualification is currently limited to
`Ornith-1.5-35B-A3B-MLX`, a **Qwen3.6-derived hybrid/non-trimmable** cache path.
That lineage is not a blanket Qwen-family support claim. Generic trimmable-KV
runtime parity remains a separate future qualification.

The research workspace remains a source of experimental evidence; experimental
worktrees, local model files, logs, generated evidence, and unrelated upstream
history stay outside this repository.

See:

- [`docs/PRODUCT_BOUNDARY.md`](docs/PRODUCT_BOUNDARY.md)
- [`docs/PHASE1_COMPUTE_CONTINUITY.md`](docs/PHASE1_COMPUTE_CONTINUITY.md)
- [`docs/PHASE1_5_MLX_STORAGE_ADAPTER.md`](docs/PHASE1_5_MLX_STORAGE_ADAPTER.md)
- [`docs/PHASE1_6_PRODUCTION_CANARY.md`](docs/PHASE1_6_PRODUCTION_CANARY.md)
- [`docs/PHASE1_6_1_P0_HARDENING.md`](docs/PHASE1_6_1_P0_HARDENING.md)
- [`docs/PHASE1_6_2_REAL_INTEGRATION_QUALIFICATION.md`](docs/PHASE1_6_2_REAL_INTEGRATION_QUALIFICATION.md)
- [`docs/COMPUTE_FREEZE_V0_1.md`](docs/COMPUTE_FREEZE_V0_1.md)
- [`docs/TRUST_DOMAIN_BOUNDARY.md`](docs/TRUST_DOMAIN_BOUNDARY.md)
- [`docs/DISTRIBUTION_BOUNDARY.md`](docs/DISTRIBUTION_BOUNDARY.md)
- [`docs/SUPPORTED_SCOPE_V0_1.md`](docs/SUPPORTED_SCOPE_V0_1.md)
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- [`docs/ROADMAP.md`](docs/ROADMAP.md)
- [`docs/RELEASE_PROCESS.md`](docs/RELEASE_PROCESS.md)
- [`docs/RELEASE_CHECKLIST.md`](docs/RELEASE_CHECKLIST.md)
- [`CHANGELOG.md`](CHANGELOG.md)
- [`SECURITY.md`](SECURITY.md)
- [`LICENSE`](LICENSE)
- [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)

## Development verification

StateBraid uses a zero-dependency standard-library test path:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Static type verification, when Pyright is available:

```bash
PYTHONPATH=src pyright src tests bench scripts
```

## License

StateBraid is licensed under the [Apache License 2.0](LICENSE). The packaged MLX
reference integration has separate upstream provenance; the Apple/mlx-lm MIT
notice is retained in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Project identity

- **Name:** StateBraid
- **Runtime:** StateBraid Runtime
- **Tagline:** Less recompute. Less redo.
- **Product scope:** Agent-aware compute continuity for long-running local agents.
