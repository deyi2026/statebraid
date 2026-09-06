# StateBraid Roadmap

## v0.1 -- boundary and reproducibility

- Freeze the three-capability product boundary.
- **DONE (Phase 1):** extract stable/active compute-continuity policy as an attributable, backend-neutral component.
- Import selected-evidence continuity as a reviewable runtime component rather than a benchmark-only experiment.
- Import provider-interruption continuity with its one-shot resume contract.
- **DONE (Phase 1.5):** establish and verify a single install/test path from a fresh checkout.
- **DONE (Phase 1.6):** validate MLX production activation as an explicit, default-off canary and restore the prior runtime afterwards.
- **DONE (Phase 1.6.1):** harden activation so StateBraid ignores legacy semantic cache tags, defaults to semantic-blind residency, and uses one generation-safety source of truth in StateBraid mode.
- Add privacy and ownership tests for cross-session cache reuse.
- Add one canonical agent benchmark suite that measures completion, duplicate work, evidence support, cache reuse, and new prefill.

## v0.2 -- backend abstraction

- **Started in Phase 1:** core compute-continuity policy is already separated from MLX-specific cache objects.
- Keep MLX as the first-class backend.
- **DONE (Phase 1.5):** define and verify a narrow transactional MLX storage adapter without depending on private trie internals.
- **Started in Phase 1.6:** expose bounded cache-policy telemetry needed to verify activation and prefix reuse.
- Define backend capability reporting for interruption metadata.

## v0.3 -- multi-session hardening

- Explicit cache namespaces / trust domains.
- Session ownership and cache-salt equivalent protection where needed.
- Crash/restart recovery tests.
- Durable cache policy experiments only after correctness gates pass.

## Deferred research

- automatic/model-authored checkpoint producer enablement;
- distributed KV tiers;
- aggressive KV quantization defaults;
- semantic memory/ranking owned by the runtime;
- large-scale continuous batching.
