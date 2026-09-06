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

StateBraid is being extracted from an active research workspace. The current repository is the clean product boundary and integration target; experimental worktrees, local model files, logs, generated evidence, and unrelated upstream history are deliberately excluded.

See:

- [`docs/PRODUCT_BOUNDARY.md`](docs/PRODUCT_BOUNDARY.md)
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- [`docs/ROADMAP.md`](docs/ROADMAP.md)
- [`SECURITY.md`](SECURITY.md)

## Project identity

**Name:** StateBraid
**Runtime:** StateBraid Runtime
**Tagline:** Less recompute. Less redo.
**Short promise:** Less recompute, less redo.
