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
- Maintain one canonical integration benchmark that detects agent-behavior regressions while reporting cache reuse, new prefill, worker health and factual compute telemetry.

## v0.2 -- backend abstraction and capability reporting

- **Started in Phase 1:** core compute-continuity policy is separated from MLX-specific cache objects.
- Keep MLX as the first-class backend while preserving a backend-neutral core.
- **DONE (Phase 1.5):** define and verify a narrow transactional MLX storage adapter without depending on private trie internals.
- **Started in Phase 1.6:** expose bounded factual cache-policy telemetry needed to verify activation and prefix reuse.
- Define backend capability reporting for exact storage, trimmability, generation-safe replay, sequence capacity and byte accounting.
- Qualify generic trimmable-KV behavior separately before claiming parity beyond the current Ornith/Qwen hybrid path.

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
