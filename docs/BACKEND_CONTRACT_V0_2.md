# Backend Contract v0.2

Backend Contract v0.2 is the adapter boundary between StateBraid's
compute-continuity policy and a model-serving runtime. It is **additive** to the
frozen Compute Contract v0.1: it does not change cache identity, stable/active
lineage, capacity, rollback, or generation-safety semantics already qualified in
v0.1.

## Ownership rule

StateBraid owns compute-continuity **semantics and policy**:

- exact namespace + token cache identity;
- stable/active lineage;
- admission/residency policy when a backend delegates those mechanics;
- transactional mutation orchestration and rollback semantics;
- actual-prefix hit attribution;
- generation-safe exact-reuse semantics;
- factual compute-continuity telemetry.

A serving backend keeps ownership of:

- model execution;
- attention kernels;
- continuous batching and scheduler execution;
- KV tensor representation and physical storage;
- KV transport, tiering, persistence, and distributed transfer.

Therefore StateBraid is not a replacement inference engine and is not a competing
KV transport/storage system. A backend may use native RAM/GPU storage, LMCache,
HiCache, NIXL, Mooncake, or another transport layer without transferring that
ownership into StateBraid.

## Capability declaration

`BackendDescriptor` declares mechanics independently from runtime qualification.
The v0.2 capabilities are:

| Capability | StateBraid contract meaning |
| --- | --- |
| `namespace_isolation` | identical tokens in different namespaces cannot resolve to the same reusable state |
| `prefix_lookup` | adapter can report the actual reusable/served prompt prefix as exact prompt + remainder evidence; observation may be pre-execution or execution-coupled |
| `admission_residency` | backend permits StateBraid to apply external admission/eviction decisions |
| `transactional_mutation` | exact capture/remove/insert/restore mechanics are available |
| `rollback` | failed mutation can restore the prior valid backend state |
| `hit_attribution` | a hit can be credited to the exact prefix that actually served it |
| `generation_safety` | exact reuse can be converted to a generation-safe replay/recompute boundary |

Capabilities are intentionally graded. An adapter may declare only a safe subset;
unsupported conformance cases are explicit `SKIP`, not implicit success. Declared
capabilities also have dependency checks: for example rollback requires
transactional mutation and hit attribution requires prefix lookup.

The current integration levels are descriptive, not marketing support tiers:

- `identity-only` -- namespace isolation only;
- `observe` -- namespace + lookup + actual-prefix attribution;
- `managed` -- observe plus externally managed admission/residency and rollback;
- `generation-safe-managed` -- managed plus generation-safe exact reuse;
- `partial` -- another mechanically declared subset.

## Lookup evidence

`LookupObservation` normalizes backend reuse evidence. The evidence may come from
a pure/pre-execution lookup API or from execution-coupled factual telemetry such
as a server response that reports the prefix actually reused. StateBraid does not
require backends to expose an unsafe intermediate exact-hit state merely to prove
generation safety.

A backend result is rejected when its uncached remainder is not an exact suffix of
the prompt, when it claims a matched prefix without a payload, or when it returns a
payload without a matched prefix. This prevents StateBraid from crediting cache
reuse from ambiguous or internally inconsistent backend telemetry.

## Conformance framework

`statebraid.backend.conformance.run_backend_conformance()` accepts an adapter-author
**test driver**. The driver is intentionally not the production serving API: it may
expose test-only fault injection and residency introspection while the real adapter
can be local, HTTP, RPC, or another transport.

The driver also exposes a test-only resident-state seeding primitive. This is
deliberately separate from the production `admission_residency` capability: a
backend that keeps its own eviction/admission authority must still be able to prove
namespace isolation, prefix lookup, hit attribution, or generation safety without
pretending that StateBraid owns its KV residency policy.

The standard v0.2 suite covers, when the corresponding capabilities are declared:

1. deterministic namespace identity across trust domains;
2. same-domain reuse and cross-domain isolation;
3. actual-prefix hit attribution;
4. stable/active successor lineage and residency;
5. independent sequence/byte capacity enforcement;
6. transactional rollback after injected mutation failure;
7. generation-safe exact reuse with a non-empty prompt remainder (N-1 replay or a larger safe recomputation).

A capability that is not declared is skipped explicitly. A capability that **is**
declared but fails its case is a conformance failure. This is the fail-closed rule
for future llama.cpp, vLLM, SGLang, or other adapters.

## MLX reference

The current MLX adapter declares all seven v0.2 capabilities and passes the
standard deterministic conformance suite. This declaration does **not** widen the
v0.1 runtime qualification: the exact MLX base, Apple Silicon platform, Ornith
hybrid/non-trimmable path, concurrency profile, default-off activation, and other
limits remain those in `SUPPORTED_SCOPE_V0_1.md`.

## llama.cpp reference

Phase 8 audits `ggml-org/llama.cpp` commit
`465e49b9cea78a68b9c244ffb48d0ee24a82873d` as a second, structurally different
backend. The public llama-server adapter intentionally declares only
`prefix_lookup`, `hit_attribution`, and `generation_safety`. It does not declare
namespace isolation, admission/residency, transactional mutation, or rollback.

This is deliberate. Current llama-server owns its slot scheduler, shared prompt
cache, and KV storage, while the shared RAM prompt cache has no StateBraid trust
namespace. StateBraid observes the actually served prefix from `timings.cache_n`
and rejects non-default trust domains rather than inventing isolation from slot
IDs. See [`LLAMA_CPP_REFERENCE_V0_2.md`](LLAMA_CPP_REFERENCE_V0_2.md).

Machine-readable inspection:

```bash
statebraid-doctor contract --json
statebraid-doctor scope --json
```

The first reports adapter mechanics; the second reports what has actually been
end-to-end qualified. Those two statements must not be conflated.
