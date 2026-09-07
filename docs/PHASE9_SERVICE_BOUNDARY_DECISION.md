# Phase 9 Service / Control-Plane Boundary Decision

Status: **architecture decision — generic service draft is not a StateBraid product
surface**.

## Context

An experimental Phase 9 worktree explored a conservative reference service with:

- `/v1/chat/completions`;
- backend registry/routing;
- trusted principal → trust-domain derivation;
- HTTP proxying;
- factual telemetry;
- MLX and llama.cpp policy adapters.

The draft was intentionally narrow: loopback-only, non-streaming, no semantic
routing, no model execution, no scheduler/KV ownership, caller namespace rejected,
and llama.cpp multi-tenant use failed closed.

The code therefore did not yet violate the compute-only boundary. The problem is
**product gravity**: once StateBraid owns a generic chat/gateway endpoint, normal
serving requirements naturally pull in authentication, TLS, retries, fallback,
model selection, health routing, rate limiting, load balancing, model lifecycle,
streaming, and eventually scheduling.

That direction would turn StateBraid from a compute-continuity layer into another
inference gateway/serving platform.

## Decision: KEEP / CUT / SPLIT

### KEEP in StateBraid

Two small mechanical primitives are product-aligned:

1. **trusted ownership → trust-domain derivation**;
2. **compatibility check for a backend already selected elsewhere**.

They live under `statebraid.integration`, not a generic service API.

### CUT from the StateBraid product surface

StateBraid will not own, by default:

- generic `/v1/chat/completions` service endpoint;
- backend/model selection;
- backend routing policy;
- retry/fallback policy;
- authentication/TLS termination;
- rate limiting/load balancing;
- model lifecycle;
- streaming protocol conversion;
- serving gateway telemetry or provider orchestration.

Backend identity is an **input** to the Harness ↔ StateBraid Integration Contract,
not a choice StateBraid makes from task/message content.

### SPLIT if a reference gateway is useful later

A runnable gateway may exist later as an external example, companion project, or
harness/gateway integration test. It should consume StateBraid contracts rather than
become the StateBraid product boundary.

The unmerged Phase 9 experimental worktree is retained only as research evidence;
it is not intended for `main` in its current service/proxy form.

## Why this is preferable

This keeps the durable architecture:

```text
Agent Harness / external serving gateway
  owns task semantics + backend selection + delivery policy
                 |
                 | backend identity + trusted trust-domain + exact tokens
                 v
StateBraid
  owns compute-continuity policy/facts only
                 |
                 | narrow backend mechanical contract
                 v
MLX / llama.cpp / future serving backend
```

A new feature can now be classified mechanically using
`HARNESS_INTEGRATION_CONTRACT_V0_1.md` rather than reopening the product-boundary
debate each time.

## Explicit non-goals following this decision

This decision is a reason **not** to add, in the next phase:

- vLLM and SGLang simultaneously;
- semantic backend/model routing;
- cache-driven tool/evidence/completion behavior;
- StateBraid working-state/checkpoint storage;
- legacy `cache_tag` admission authority;
- KV restart persistence without a correctness model;
- distributed KV / quantized KV / multi-model serving merely to expand a matrix.

The next backend should be chosen from real deployment demand after the contracts
and current LFL integration remain clean.
