# StateBraid

**Agent-aware compute-continuity runtime for long-running local agents.**

StateBraid is built around one practical goal:

> Less recompute. Less redo.

The v0.1 distribution version is **`0.1.0`**. Source metadata, protected-main
verification, and the immutable `v0.1.0` tag are separate release gates; preparing
the final version string does not by itself create a release or widen the supported
runtime scope.

StateBraid directly owns the **less recompute** half of that promise. It preserves
mechanical serving state so long-running agents do not repeatedly rebuild the same
model prefix. The **less redo** half is an integration outcome: task, evidence and
execution continuity remain the responsibility of the agent harness and the model,
not a second semantic decision system inside StateBraid.

## Runtime support status

StateBraid separates **reference-qualified runtime support** from narrower backend
qualification evidence. That distinction is intentional: a backend can prove that
StateBraid's compute-continuity contract composes safely with it before every model,
platform, isolation mode, and serving topology is claimed as production-supported.

| Runtime / backend | Platform | Current status |
| --- | --- | --- |
| MLX-LM + StateBraid reference patch | Apple Silicon / macOS | **v0.1 reference-qualified** |
| llama.cpp + real GGUF | Apple Silicon / macOS | **real-model qualification candidate**; CPU/Accelerate + Metal safety evidence PASS, while `runtime_qualified=false` remains deliberate |
| llama.cpp + the same real GGUF | Linux x86_64 | **planned qualification**; deferred from the v0.1 release gate |
| llama.cpp + CUDA | Linux x86_64 / NVIDIA | **planned supplement** after Linux CPU qualification |
| vLLM / SGLang | Linux / GPU | **future Backend Contract integrations**, not current v0.1 runtime support |

The Apple llama.cpp evidence used the exact audited upstream source
`465e49b9cea78a68b9c244ffb48d0ee24a82873d` with a real 16.27 GB
Qwen3.6-derived MoE GGUF. Both CPU/Accelerate and full-Metal-offload runs passed the
cold/exact/prefix/divergence/A-B-A/multi-turn/erase/restart safety matrix, including
real generation after exact reuse. This is materially stronger than the earlier
tiny-model capability canary, but it is **not** a blanket claim that StateBraid
supports every GGUF, every llama.cpp revision, or arbitrary multi-tenant llama-server
deployments.

In particular, the current public llama-server prompt cache does not expose the
request-scoped trust namespace required for StateBraid's MLX-style multi-domain
isolation. The current llama.cpp adapter therefore remains single-domain
`local-default`, `integration_level=partial`, and `runtime_qualified=false` until a
future support-matrix change is made through the normal protected qualification
process.

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
- a narrow MLX adapter as the first managed backend integration;
- a public-HTTP llama.cpp adapter as the second, deliberately partial backend proof.

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
 The normative cross-layer boundary is now machine-readable as
**Harness ↔ StateBraid Integration Contract v0.1**: the Harness/gateway chooses the
backend and supplies only trusted ownership/trust-domain, exact token identity and
mechanical limits; StateBraid returns factual compute-continuity results only.

StateBraid deliberately does **not** ship a generic chat/inference gateway. A Phase
9 `/v1/chat/completions` service experiment was reviewed but kept out of the product
surface because backend routing/proxy ownership would create pressure toward auth,
retry/fallback, model selection, load balancing and serving-platform scope. The two
mechanical pieces worth keeping -- trusted ownership → trust domain and compatibility
checking for an already-selected backend -- live under `statebraid.integration`.

### Backend Contract v0.2

StateBraid now separates its compute policy from serving-runtime mechanics through
a capability-based **Backend Contract v0.2**. Backends may declare namespace,
prefix lookup, admission/residency, transaction/rollback, actual-prefix hit
attribution, and generation-safety capabilities independently; they do not have to
implement the complete surface in one step. The reusable conformance runner turns
unsupported capabilities into explicit skips and treats failures of declared
capabilities as hard failures.

StateBraid does **not** own model execution, attention kernels, continuous batching,
physical KV storage, or KV transport/tiering. Those remain backend responsibilities.
This keeps StateBraid usable above MLX-LM, llama.cpp, vLLM, SGLang, or future
serving/storage stacks without becoming a second inference engine or KV server.

Inspect the machine-readable contract with:

```bash
statebraid-doctor contract --json
statebraid-doctor integration --json
```

See [`docs/BACKEND_CONTRACT_V0_2.md`](https://github.com/deyi2026/statebraid/blob/main/docs/BACKEND_CONTRACT_V0_2.md).

The second backend proof is llama.cpp. Against audited upstream
`465e49b9cea78a68b9c244ffb48d0ee24a82873d`, StateBraid uses only public
llama-server timing/slot/property APIs. It declares actual-prefix observation, hit
attribution, and audited exact-reuse generation safety, while **not** claiming trust-domain
isolation, cache admission/residency authority, transactions, or rollback.

```bash
statebraid-doctor llama-cpp --url http://127.0.0.1:8080 --json
```

The doctor fails closed unless both the public API surface and the exact audited
source commit match. The same exact source has now also passed an Apple/macOS
real-GGUF qualification candidate run on CPU/Accelerate and Metal. That evidence
still does not widen the v0.1 Supported Scope or change the committed
`runtime_qualified=false` metadata. See
[`docs/LLAMA_CPP_REFERENCE_V0_2.md`](https://github.com/deyi2026/statebraid/blob/main/docs/LLAMA_CPP_REFERENCE_V0_2.md).

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

See [`docs/SUPPORTED_SCOPE_V0_1.md`](https://github.com/deyi2026/statebraid/blob/main/docs/SUPPORTED_SCOPE_V0_1.md), or query the
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

Apply that patch only to the exact qualified MLX-LM base, then install that exact
patched checkout into the **same Python environment** that will run the server. The
upstream package metadata installs its MLX dependency requirements; a clean patch
apply by itself is not an installation or compatibility result:

```bash
git clone https://github.com/ml-explore/mlx-lm.git
cd mlx-lm
git checkout 6d21ce4b065a2e163fa6de76a9936c61aeb5784a
git apply --check ../statebraid-mlx.patch
git apply ../statebraid-mlx.patch
python -m pip install .
statebraid-doctor mlx
```

Run the doctor from that same environment before activation. It must exit `0`; an
unpatched, unavailable, or incompatible MLX-LM installation fails closed.

StateBraid activation remains explicit and default-off:

```bash
MLX_LM_STATEBRAID=1 python -m mlx_lm.server --model <model> ...
```

Rollback is mechanical: stop the server, unset `MLX_LM_STATEBRAID`, and restart
the patched backend on its native `LRUPromptCache` path. A request may provide
`cache_namespace`; multi-tenant callers must have a trusted authenticated layer
derive that value rather than accepting an arbitrary tenant name from an
untrusted client.

See [`docs/DISTRIBUTION_BOUNDARY.md`](https://github.com/deyi2026/statebraid/blob/main/docs/DISTRIBUTION_BOUNDARY.md) for the exact
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
[`docs/COMPUTE_FREEZE_V0_1.md`](https://github.com/deyi2026/statebraid/blob/main/docs/COMPUTE_FREEZE_V0_1.md).

Phase D aligns the product definition with that frozen compute contract: StateBraid
is no longer described as the owner of selected-evidence, interruption recovery,
or other agent-layer continuity mechanisms.

The real model qualification is currently limited to
`Ornith-1.5-35B-A3B-MLX`, a **Qwen3.6-derived hybrid/non-trimmable** cache path.
That lineage is not a blanket Qwen-family support claim. Generic trimmable-KV
runtime parity remains a separate future qualification.

Separately, the llama.cpp adapter has now passed a real-model Apple qualification
candidate using a portable Q4_K GGUF on both CPU/Accelerate and Metal. The next
cross-platform gate is Linux x86_64 with the **same GGUF bytes**, the same audited
llama.cpp source, and the same mechanical canary. A CUDA supplement follows only
after the Linux CPU qualification. If those gates pass, a later protected PR may
promote llama.cpp to a second reference runtime; until then, the v0.1 support matrix
remains MLX-only. Broader GGUF/model profiles and additional backends such as vLLM
or SGLang require their own capability and runtime qualification rather than an
implicit support claim.

The research workspace remains a source of experimental evidence; experimental
worktrees, local model files, logs, generated evidence, and unrelated upstream
history stay outside this repository.

See:

- [`docs/PRODUCT_BOUNDARY.md`](https://github.com/deyi2026/statebraid/blob/main/docs/PRODUCT_BOUNDARY.md)
- [`docs/BACKEND_CONTRACT_V0_2.md`](https://github.com/deyi2026/statebraid/blob/main/docs/BACKEND_CONTRACT_V0_2.md)
- [`docs/HARNESS_INTEGRATION_CONTRACT_V0_1.md`](https://github.com/deyi2026/statebraid/blob/main/docs/HARNESS_INTEGRATION_CONTRACT_V0_1.md)
- [`docs/PHASE9_SERVICE_BOUNDARY_DECISION.md`](https://github.com/deyi2026/statebraid/blob/main/docs/PHASE9_SERVICE_BOUNDARY_DECISION.md)
- [`docs/LLAMA_CPP_REFERENCE_V0_2.md`](https://github.com/deyi2026/statebraid/blob/main/docs/LLAMA_CPP_REFERENCE_V0_2.md)
- [`docs/PHASE1_COMPUTE_CONTINUITY.md`](https://github.com/deyi2026/statebraid/blob/main/docs/PHASE1_COMPUTE_CONTINUITY.md)
- [`docs/PHASE1_5_MLX_STORAGE_ADAPTER.md`](https://github.com/deyi2026/statebraid/blob/main/docs/PHASE1_5_MLX_STORAGE_ADAPTER.md)
- [`docs/PHASE1_6_PRODUCTION_CANARY.md`](https://github.com/deyi2026/statebraid/blob/main/docs/PHASE1_6_PRODUCTION_CANARY.md)
- [`docs/PHASE1_6_1_P0_HARDENING.md`](https://github.com/deyi2026/statebraid/blob/main/docs/PHASE1_6_1_P0_HARDENING.md)
- [`docs/PHASE1_6_2_REAL_INTEGRATION_QUALIFICATION.md`](https://github.com/deyi2026/statebraid/blob/main/docs/PHASE1_6_2_REAL_INTEGRATION_QUALIFICATION.md)
- [`docs/COMPUTE_FREEZE_V0_1.md`](https://github.com/deyi2026/statebraid/blob/main/docs/COMPUTE_FREEZE_V0_1.md)
- [`docs/TRUST_DOMAIN_BOUNDARY.md`](https://github.com/deyi2026/statebraid/blob/main/docs/TRUST_DOMAIN_BOUNDARY.md)
- [`docs/DISTRIBUTION_BOUNDARY.md`](https://github.com/deyi2026/statebraid/blob/main/docs/DISTRIBUTION_BOUNDARY.md)
- [`docs/SUPPORTED_SCOPE_V0_1.md`](https://github.com/deyi2026/statebraid/blob/main/docs/SUPPORTED_SCOPE_V0_1.md)
- [`docs/ARCHITECTURE.md`](https://github.com/deyi2026/statebraid/blob/main/docs/ARCHITECTURE.md)
- [`docs/ROADMAP.md`](https://github.com/deyi2026/statebraid/blob/main/docs/ROADMAP.md)
- [`docs/RELEASE_PROCESS.md`](https://github.com/deyi2026/statebraid/blob/main/docs/RELEASE_PROCESS.md)
- [`docs/RELEASE_CHECKLIST.md`](https://github.com/deyi2026/statebraid/blob/main/docs/RELEASE_CHECKLIST.md)
- [`CHANGELOG.md`](https://github.com/deyi2026/statebraid/blob/main/CHANGELOG.md)
- [`SECURITY.md`](https://github.com/deyi2026/statebraid/blob/main/SECURITY.md)
- [`LICENSE`](https://github.com/deyi2026/statebraid/blob/main/LICENSE)
- [`THIRD_PARTY_NOTICES.md`](https://github.com/deyi2026/statebraid/blob/main/THIRD_PARTY_NOTICES.md)

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

StateBraid is licensed under the [Apache License 2.0](https://github.com/deyi2026/statebraid/blob/main/LICENSE). The packaged MLX
reference integration has separate upstream provenance; the Apple/mlx-lm MIT
notice is retained in [THIRD_PARTY_NOTICES.md](https://github.com/deyi2026/statebraid/blob/main/THIRD_PARTY_NOTICES.md).

## Project identity

- **Name:** StateBraid
- **Runtime:** StateBraid Runtime
- **Tagline:** Less recompute. Less redo.
- **Product scope:** Agent-aware compute continuity for long-running local agents.
