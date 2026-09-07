# StateBraid Roadmap

## v0.1 -- compute boundary and reproducibility

- **DONE (Phase 1):** extract stable/active compute-continuity policy as an attributable, backend-neutral component.
- **DONE (Phase 1.5):** establish a narrow transactional MLX storage adapter and a reproducible fresh-checkout install/test path.
- **DONE (Phase 1.6):** validate MLX production activation as an explicit, default-off canary and restore the prior runtime afterwards.
- **DONE (Phase 1.6.1):** remove legacy semantic cache authority from the StateBraid path and use one generation-safety source of truth when StateBraid is active.
- **DONE (Phase 1.6.2):** qualify the mechanical policy through an immutable, unchanged LFL client path with equivalent completion/evidence/tool/cache behavior and real N-1 exact-hit safety.
- **DONE (Phase C):** freeze the qualified compute surface as Compute Contract v0.1 with public-subset and black-box compatibility gates; keep activation default-off and CognitivePromptCache as rollback/control.
- **DONE (Phase D):** align product/architecture/package/security documentation to a compute-only StateBraid boundary; agent task/evidence/execution continuity remains harness-owned.
- **DONE (Trust-Domain Boundary):** add explicit request-scoped cache namespaces,
  cross-domain isolation tests, hostile-input validation, and a real single-model
  A/B/A canary; authenticated tenant-to-namespace assignment remains deployment
  infrastructure rather than StateBraid semantics.
- **DONE (Distribution Boundary):** ship the StateBraid core independently from
  MLX-LM, package a SHA256-frozen reference patch against exact upstream MLX-LM
  `6d21ce4`, expose capability-based `statebraid-doctor` and patch-export tooling,
  preserve explicit/default-off activation and native rollback, and validate the
  clean reference with upstream regressions plus a real single-model canary.
- **DONE (Supported Scope):** separate backend-neutral Compute Contract v0.1 from
  the narrower runtime qualification; freeze the exact Apple Silicon/MLX
  reference profile, Qwen3.6-derived Ornith hybrid/non-trimmable evidence,
  default-off activation, trust-domain conditions, and explicit unqualified
  runtime modes as machine-readable package metadata plus documentation.
- **DONE (CI / Repo Protection):** enforce zero-model unit, Python 3.11-3.14,
  Pyright, contract, privacy and package-content checks through GitHub Actions;
  protect `main` for everyone with strict required checks, PR flow, linear
  history, conversation resolution, and no force-push/deletion.
- **DONE (Release Preparation):** select Apache License 2.0 for the StateBraid distribution,
  retain Apple/mlx-lm provenance separately, adopt PEP 639 license metadata,
  package legal/release documentation, pass the release-candidate audit, and advance
  final-preparation source metadata to `0.1.0`. Formal release tagging remains a
  separate gate on the exact protected-main SHA after post-merge CI and final
  fresh-clone verification.
- Maintain one canonical integration benchmark that detects agent-behavior regressions while reporting cache reuse, new prefill, worker health and factual compute telemetry.

## v0.2 -- backend abstraction and capability reporting

- **Started in Phase 1:** core compute-continuity policy is separated from MLX-specific cache objects.
- Keep MLX as the first-class backend while preserving a backend-neutral core.
- **DONE (Phase 1.5):** define and verify a narrow transactional MLX storage adapter without depending on private trie internals.
- **Started in Phase 1.6:** expose bounded factual cache-policy telemetry needed to verify activation and prefix reuse.
- **DONE (Phase 7 / Backend Contract v0.2):** define a capability-based backend
  contract for namespace isolation, prefix lookup, admission/residency,
  transaction/rollback, actual-prefix hit attribution, and generation-safe exact
  reuse; add reusable PASS/SKIP/FAIL conformance and machine-readable ownership.
- **DONE (Phase 7 MLX proof):** the existing MLX adapter declares the full
  generation-safe-managed capability set and passes the deterministic conformance
  suite without changing Compute Contract v0.1 behavior or widening v0.1 runtime
  qualification.
- **DONE (Phase 8):** audit exact llama.cpp upstream `465e49b9`, add a public-HTTP
  partial adapter with no upstream patch, and prove actual-prefix hit attribution
  plus generation-safe exact reuse without claiming namespace/admission/transaction
  authority. The final adapter exact-source tiny runtime canary passed cold 0/42 ->
  prefix 42/89 -> exact-safe 88/89; deterministic/package/privacy/fresh-install
  gates, protected PR checks, and post-merge main CI all pass. The v0.1 production
  runtime scope remains MLX-only.
- **DONE (Apple llama.cpp real-GGUF L1):** on the same audited llama.cpp source,
  exercise a real 16.27 GB Qwen3.6-derived MoE GGUF on Apple Silicon/macOS first with
  CPU/Accelerate and then with full Metal offload. Cold/exact/generation-safe,
  extension/divergence, A-B-A stale-state, multi-turn, erase, restart, fail-closed,
  and unchanged-agent integration checks all pass. This is a **runtime-qualification
  candidate evidence set**, not an automatic v0.1 support-matrix expansion;
  `runtime_qualified=false` and single-domain llama.cpp boundaries remain intact.
- **PLANNED / DEFERRED (Linux llama.cpp real-GGUF L2):** repeat the same qualification
  on native Linux x86_64 using the **same GGUF bytes**, exact audited llama.cpp SHA,
  and the same mechanical canary. CPU qualification is the primary cross-platform
  gate; CUDA is a separate serial supplement after CPU PASS. L2 is deliberately not
  a v0.1 release blocker.
- **DONE (Boundary Freeze / post-Phase 8):** freeze Harness ↔ StateBraid
  Integration Contract v0.1; backend/model selection remains Harness/gateway-owned,
  semantic task/evidence/checkpoint/tool/completion fields are mechanically excluded,
  and legacy `cache_tag` has no StateBraid admission/residency authority.
- **DONE (Backend observation semantics):** require every `prefix_lookup` adapter to
  declare passive vs execution-coupled observation and backend-state mutation risk;
  require generation-safety declarations to include a narrow qualification profile.
- **CANCELLED AS PRODUCT SURFACE (Phase 9 service draft):** do not merge the generic
  `/v1/chat/completions` registry/router/proxy experiment into StateBraid. Retain
  only trusted ownership→trust-domain derivation and an already-selected-backend
  capability gate as library primitives. A future runnable gateway belongs in an
  external harness/serving layer or companion example.
- Qualify generic trimmable-KV behavior separately before claiming parity beyond
  the exact v0.1 reference profile.
- After Linux x86_64 L2, decide through a narrow protected PR whether llama.cpp is
  promoted to a second reference runtime. Do not infer blanket support for arbitrary
  GGUF files, llama.cpp revisions, multi-tenant shared-cache deployments, or model
  families from one qualified profile.
- Add further backend adapters such as vLLM or SGLang only when their public serving
  surfaces can satisfy a useful subset of Backend Contract v0.2 without moving model
  execution, routing, batching, or KV transport ownership into StateBraid.

## v0.3 -- multi-session compute hardening

- **Started:** explicit cache namespaces / trust domains are implemented for the
  qualified MLX path; broader backend parity remains future work.
- Session ownership and cache-salt-equivalent protection where needed.
- Crash/restart recovery for compute/cache state where correctness can be proven.
- Durable cache-policy experiments only after correctness gates pass.

## Outside the StateBraid roadmap -- agent harness ownership

The following are intentionally not future StateBraid features unless the product
boundary is explicitly reconsidered:

- selected raw evidence and evidence ranking;
- fold/receipt and working-state/checkpoint policy;
- provider-interruption task continuation;
- Goal/handoff state;
- SubAgent ownership/orchestration;
- ExecutionWorkspace and durable session/event state;
- task planning, tool selection, or completion judgment.

These belong to the agent harness and/or model. StateBraid may be qualified against
them as an unchanged client, but it does not implement them.

## Deferred StateBraid research

- distributed KV tiers;
- aggressive KV quantization defaults;
- large-scale continuous batching;
- persistent compute-state recovery across process restart;
- additional serving backends after the MLX contract is stable.
