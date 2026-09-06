# StateBraid

**Agent-aware inference runtime for long-running local agents.**

StateBraid is being built around one practical goal:

> Less recompute. Less redo.

For long-running agents, speed is not only about tokens per second. A useful runtime must avoid both unnecessary recomputation and unnecessary rework. StateBraid therefore treats two forms of continuity as first-class runtime concerns:

- **Compute continuity** — stable-prefix reuse, active-tail reuse, bounded KV/prompt-cache residency, and safe recovery under cache pressure.
- **Reasoning continuity** — preserve model-selected original evidence, compact old work without losing provenance, and resume cleanly after provider-side truncation.

In short: **less recompute, less redo.**

## v0.1 product boundary

StateBraid v0.1 is intentionally narrow. It combines three runtime capabilities:

1. **Stable/active compute continuity**
   - shared stable prefix reuse across agent turns/sessions;
   - generation-safe cache hits;
   - explicit byte budget and transient capacity;
   - stable + active working-set protection;
   - transactional cache mutation / rollback on failed admission.

2. **Selected-evidence context continuity**
   - the model selects which already-observed tool evidence must remain directly visible;
   - selected evidence remains the original assistant tool declaration + original tool result;
   - the program validates protocol groups and resource bounds, but does not decide semantic relevance;
   - unselected old evidence may fall back to recoverable receipts.

3. **Interrupted-generation continuity**
   - provider `length` / `max_tokens` output is treated as an interrupted partial, not a completed answer;
   - the exact partial is retained;
   - the next real user ingress can resume from that partial without rewriting the user's message.

## Non-goals for v0.1

StateBraid v0.1 is **not**:

- a general distributed inference platform competing with vLLM or SGLang;
- an autonomous task planner;
- a semantic evidence ranker controlled by program heuristics;
- a hidden-chain-of-thought persistence system;
- a replacement for the agent harness or tool layer;
- a promise that checkpoint production is enabled by default.

The runtime supplies capabilities and mechanical boundaries. The model keeps ownership of semantic judgment.

## Current status

Phase 1 compute continuity is now extracted into a backend-neutral core. The repository contains stable/active working-set policy, sequence + byte budget planning, transactional backend coordination, and exact-hit generation safety without importing the MLX-LM fork into the core package.

Phase 1.5 adds a narrow MLX storage adapter backed by a public transactional-storage capability. StateBraid still does not access MLX-LM private trie/LRU fields.

Phase 1.6 validates that adapter in a real MLX server behind an explicit opt-in activation. The canary preserves a single cache-policy authority, rejects StateBraid + CognitivePromptCache coexistence, and keeps the normal server path unchanged by default. The successful canary does **not** make StateBraid the default production cache policy.

Phase 1.6.1 removes the remaining legacy semantic cache authority from the StateBraid path. Phase 1.6.2 then qualifies the hardened mechanical policy through an unchanged, immutable LFL snapshot: task/evidence/tool behavior and cache/new-prefill accounting match the Cognitive control, real exact-hit N-1 replay remains generation-safe, and the prior Cognitive runtime is restored after testing.

Phase 1.6/1.6.1 qualification is currently limited to the **Ornith/Qwen hybrid non-trimmable** path. Phase 1.6.1 also hardens the boundary to be semantic-blind: legacy agent labels such as `goal`, `rules`, `evidence`, or `identity` do not gain default pin/residency authority. StateBraid admission is based on token identity, observed reuse, exact lineage, and resource bounds. Generic trimmable-KV parity remains a separate future qualification.

The research workspace remains a source of experimental evidence; experimental worktrees, local model files, logs, generated evidence, and unrelated upstream history stay outside this repository.

See:

- [`docs/PRODUCT_BOUNDARY.md`](docs/PRODUCT_BOUNDARY.md)
- [`docs/PHASE1_COMPUTE_CONTINUITY.md`](docs/PHASE1_COMPUTE_CONTINUITY.md)
- [`docs/PHASE1_5_MLX_STORAGE_ADAPTER.md`](docs/PHASE1_5_MLX_STORAGE_ADAPTER.md)
- [`docs/PHASE1_6_PRODUCTION_CANARY.md`](docs/PHASE1_6_PRODUCTION_CANARY.md)
- [`docs/PHASE1_6_1_P0_HARDENING.md`](docs/PHASE1_6_1_P0_HARDENING.md)
- [`docs/PHASE1_6_2_REAL_INTEGRATION_QUALIFICATION.md`](docs/PHASE1_6_2_REAL_INTEGRATION_QUALIFICATION.md)
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- [`docs/ROADMAP.md`](docs/ROADMAP.md)
- [`SECURITY.md`](SECURITY.md)
- [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)

## Development verification

StateBraid Phase 1 uses a zero-dependency standard-library test path:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Static type verification, when Pyright is available:

```bash
PYTHONPATH=src pyright src tests
```

## Project identity

**Name:** StateBraid
**Runtime:** StateBraid Runtime
**Tagline:** Less recompute. Less redo.
**Short promise:** Less recompute, less redo.
