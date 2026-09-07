# llama.cpp Managed Storage M1

This document records the experimental StateBraid-managed RAM storage path for
`llama.cpp`. It is deliberately separate from the stock Phase 8 observation
adapter described in `LLAMA_CPP_REFERENCE_V0_2.md`.

M1 proves that StateBraid can own cache residency/lifecycle policy while
`llama.cpp` continues to own model execution, scheduler behavior, KV/SSM
representation, checkpoints, and physical state transport. It does **not** widen
the v0.1 supported runtime matrix and remains `runtime_qualified=false`.

## Frozen implementation identity

The managed server prototype is an isolated local branch based on the audited
upstream source:

- upstream llama.cpp base: `465e49b9cea78a68b9c244ffb48d0ee24a82873d`;
- managed handle implementation: `29cad05988c9c48ee26ded83764ae70ae6edf665`;
- exclusive-policy `clear` primitive: `6e7d910135a4ef586aa89b41e2ceaa2058b2defa`;
- loopback-only control-plane hardening: `0f75058ccb5c4e0d7bd029d37678435eb0d2458c`;
- exact-token capture binding: `04329aacab48f91c79cd33490c2b4b33b29a7ef5`;
- StateBraid adapter requires `build_info` matching the final
  `04329aacab48f91c79cd33490c2b4b33b29a7ef5` reference.

The patch is opt-in through `--statebraid-managed-cache`. Startup fails closed if
native `--cache-ram` is non-zero, preventing two independent admission/eviction
policies from running at once. M1 also fails closed unless `--host` is loopback
(`localhost`, `127.0.0.1`, or `::1`). The StateBraid adapter independently enforces
the same loopback-only base-URL boundary. Authenticated remote transport remains a
separate qualification task.

## Managed server contract

`GET /statebraid/cache` reports one process/model-instance epoch and the opaque
resident handles currently owned by the managed store. `POST /statebraid/cache`
accepts four narrow actions:

| Action | Effect |
| --- | --- |
| `clear` | clear the selected live slot before StateBraid chooses a resident state |
| `capture` | copy the current slot prompt/checkpoint/sequence state into a new opaque RAM handle |
| `restore` | non-destructively restore an existing handle into the selected exact slot |
| `drop` | retire the handle from the managed store |

All mutations require the current epoch. Slot IDs are exact and do not inherit
llama.cpp's modulo-wrapping behavior. Restart/model unload changes the epoch and
invalidates all prior handles.

`n_bytes` is **serialized state-payload accounting**: target/draft sequence-state
bytes plus prompt checkpoint payloads. It is suitable for StateBraid's logical
working-set byte budget. It is not RSS, macOS physical footprint, GPU allocation,
or a promise that `drop` immediately returns the same number of physical pages to
the operating system.

## StateBraid adapter boundary

The managed integration lives in `statebraid.adapters.llama_cpp_managed`; the
stock `statebraid.adapters.llama_cpp` observation adapter remains unchanged.

M1 exposes two machine-readable capability layers. The low-level storage adapter
declares only `transactional_mutation`; it intentionally rejects direct prefix
lookup so callers cannot bypass StateBraid's residency choice. The managed facade
declares:

- `prefix_lookup`;
- `admission_residency`;
- `transactional_mutation`;
- `hit_attribution`;
- `generation_safety`.

It intentionally does **not** declare `namespace_isolation`. Only the existing
`local-default` single trust domain is accepted.

It also intentionally does **not** declare Backend Contract `rollback` yet.
StateBraid can roll back its local key-to-handle registry after an injected
pre-commit mutation failure, but physical handle retirement is a post-commit GC
step. Until the remote API has a separately qualified atomic commit/abort boundary,
that narrower guarantee must not be promoted into full backend rollback.

The working-set flow is:

```text
StateBraid WorkingSetPolicy
        |
        v
CacheCoordinator
        |
        v
local CacheKey -> opaque handle registry
        |
        +-- prepare: clear live slot -> choose exact-token LCP -> restore(handle)
        +-- capture: server capture_current -> opaque handle
        +-- commit: update stable/active residency -> flush unreferenced drops
        +-- failure path: restore old local bindings before any physical drop occurs
        |
        v
llama.cpp managed RAM state store
```

Physical handle retirement is deferred until the StateBraid policy transaction
commits. This is important: `CacheCoordinator.remove()` only unbinds a handle
locally and queues it for GC. If a later mutation fails, rollback can restore the
old bindings without reconstructing KV/SSM bytes in Python. Newly captured but
unbound handles are explicitly dropped on admission rejection or transaction
failure.

If a drop request loses its HTTP response after the server has already applied the
deletion, the adapter re-reads the managed store under the same epoch and treats an
already-absent handle as converged success. If physical GC remains unresolved, the
pending handle/bytes stay visible in adapter telemetry and the backend refuses to
capture additional state until cleanup can be reconciled. This preserves the
logical working-set budget from silently growing after a cleanup failure without
overclaiming atomic physical rollback.

Before every managed request, StateBraid issues `clear(id_slot)` even when it
chooses to restore no state. This prevents the previous live slot from becoming a
second, hidden residency policy.

Candidate restore is not counted as a hit. The facade performs the bounded
`/completion` probe after `clear -> select -> restore`, verifies that factual
`timings.cache_n` does not exceed the selected exact-token LCP, and only then
credits the resident state when `cache_n > 0`. A non-zero cache result when no
handle was selected is treated as hidden reuse and fails closed.

## Deterministic qualification

The llama.cpp branch includes a tiny-model server test that does not depend on the
16.27 GB real GGUF. It covers:

- opt-in disabled behavior;
- native-RAM/managed split-brain startup rejection;
- non-loopback bind rejection;
- capture/list/drop lifecycle;
- repeated non-destructive restore;
- invalid/stale epoch, invalid slot, unknown handle, malformed request and empty
  capture fail-closed behavior;
- restart epoch invalidation.

Current result: **6/6 PASS**. Adjacent upstream slot save/restore, slot erase, and
native RAM clear/restore tests also pass when run in isolated processes.

StateBraid adapter tests additionally inject transaction failures, hidden-reuse
and LCP-overclaim observations, response loss after physical drop, and unresolved
physical GC. The old registry is restored on pre-commit failure, new unbound
handles are removed, unresolved GC blocks new capture, and policy hit accounting
is driven only by factual completion telemetry. The managed/stock/policy target
set is **48 PASS** and the complete StateBraid suite is **130 PASS / 5 skipped /
100 subtests PASS** after the exact-token integration hardening.

## Real server evidence

A real tiny llama-server built from the final exact-token M1 source
`04329aacab48f91c79cd33490c2b4b33b29a7ef5` was driven through the formal
StateBraid managed facade on one isolated slot. Capture supplied the exact
expected token IDs and the server rejected identity mismatch before allocating a
handle. A 442-token stable state was captured, then a 471-token extension
executed through the facade's atomic
`clear -> select -> restore -> completion -> factual-hit` path with:

- `cache_n = 442`;
- `prompt_n = 29`.

The stable entry remained at zero policy hits after cold execution, capture, and
restore; it advanced to one hit only after the completion response reported
`cache_n = 433`.

After admitting both stable and active states, `trim_to(n_sequences=1)` reduced
the physical server store to one handle. The final server-reported payload size
was 288,328 bytes and matched StateBraid policy byte accounting exactly after the
trim.

The larger real-GGUF M1 experiment separately exercised a real autonomous
`read_file` tool call interrupted by another session. With the same 443-token
continuation prompt, tuned native llama.cpp RAM cache recomputed all 443 prompt
tokens, while StateBraid-managed RAM restored 396 tokens and processed 47 new
tokens. Forward and reverse execution order produced the same result and the same
final answer.

These results establish a real managed-storage prototype. They do not establish
generic llama.cpp production support.

## Memory-accounting boundary

Real-GGUF churn showed that live StateBraid payload accounting and OS physical
footprint do not move one-for-one. Dropping all handles released object ownership,
but the process could retain allocator high-water pages for later reuse. Repeating
the same churn did not show linear footprint growth, so the observed behavior was
consistent with allocator/VM retention rather than a demonstrated leak.

A later production qualification should therefore keep two distinct metrics:

1. StateBraid logical resident payload bytes for policy/capacity decisions;
2. platform process/device footprint telemetry for pressure and operational
   safety.

## Promotion gate

Do not change `SUPPORTED_SCOPE_V0_1.md` or the stock llama.cpp descriptor because
M1 exists. Promotion to a second reference runtime still requires a deliberate
protected decision and broader qualification, including the deferred native Linux
x86_64 same-GGUF run. Multi-trust-domain isolation, broader model families,
multi-slot/concurrency, speculative decoding, and OS-pressure behavior remain
separate qualification work.
