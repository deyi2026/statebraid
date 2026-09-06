# StateBraid Roadmap

## v0.1 -- boundary and reproducibility

- Freeze the three-capability product boundary.
- Import the stable/active compute-continuity implementation as an attributable, reviewable component.
- Import selected-evidence continuity as a reviewable runtime component rather than a benchmark-only experiment.
- Import provider-interruption continuity with its one-shot resume contract.
- Establish a single install/test path from a fresh checkout.
- Add privacy and ownership tests for cross-session cache reuse.
- Add one canonical agent benchmark suite that measures completion, duplicate work, evidence support, cache reuse, and new prefill.

## v0.2 -- backend abstraction

- Separate StateBraid semantic contracts from MLX-specific cache objects.
- Keep MLX as the first-class backend.
- Define a backend capability interface for prefix reuse, cache telemetry, and interruption metadata.

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
