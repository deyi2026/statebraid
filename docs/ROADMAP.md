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
  package legal/release documentation, and advance source metadata to
  `0.1.0rc1`. Formal release tagging remains gated on the final release-readiness
  audit.
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
- **NEXT (Phase 8):** use llama.cpp as the second, structurally different backend
  proof. Prefer public server/slot/cache capabilities; add only the smallest
  auditable patch if a required mechanical capability is absent.
- Qualify generic trimmable-KV behavior separately before claiming parity beyond
  the exact v0.1 reference profile.

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
