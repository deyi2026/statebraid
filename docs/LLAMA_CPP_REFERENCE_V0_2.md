# llama.cpp Backend Reference -- Phase 8

Phase 8 uses `llama.cpp` as the first structurally different backend proof for
Backend Contract v0.2. It deliberately does **not** turn StateBraid into a
llama.cpp scheduler, slot manager, KV store, or KV transport.

## Audited upstream

The source audit is pinned to:

- repository: `ggml-org/llama.cpp`;
- commit: `465e49b9cea78a68b9c244ffb48d0ee24a82873d`;
- audit date: 2026-09-07.

No llama.cpp source is vendored and Phase 8 adds no upstream patch. The adapter
uses only the public llama-server HTTP surface.

`GET /props` includes llama-server `build_info`, which contains a build commit
hash. `statebraid-doctor llama-cpp` therefore binds Phase 8 compatibility to the
exact audited source. A server from another commit may expose a similar API shape,
but the doctor fails closed until that source revision is separately audited.
Reachability, source commit, and exact reference match remain separate fields so
operators can distinguish an offline server from an unaudited one.

The execution adapter enforces the same source boundary independently of the
doctor. Before every `/completion` observation it reads `/props`, requires the
audited commit and a positive `total_slots`, then reads `/slots` and requires the
valid slot-ID count to agree with `total_slots`. Only after those checks pass may a
model request be sent. This prevents callers from bypassing source qualification by
constructing `LlamaCppHTTPAdapter` directly.

## Public surface used

The adapter relies on these public behaviors from the audited source:

- `POST /completion` accepts explicit token IDs, `id_slot`, `cache_prompt`, and
  bounded `n_predict`;
- completion `timings.cache_n` reports the number of prompt tokens actually reused
  from cache, while `timings.prompt_n` reports prompt tokens processed;
- the bounded StateBraid observation explicitly sets `n_cache_reuse=0` and requires
  `cache_n + prompt_n == prompt_length`, so unrelated chunk-shift accounting cannot
  be mistaken for a contiguous-prefix hit;
- exact prompt reuse is made generation-safe in the audited llama-server source by
  ensuring at least one prompt token is evaluated; when hybrid/SWA checkpoint state
  cannot satisfy that boundary, the server may safely recompute a shorter prefix or
  the full prompt instead;
- `GET /slots` reports concrete slot IDs and slot state;
- `GET /props` reports `build_info` and other server properties.

The server also exposes slot save/restore/erase when `--slot-save-path` is enabled.
Phase 8 intentionally does **not** map those endpoints to StateBraid transactional
mutation/rollback capability. They are backend lifecycle operations, and public
upstream evidence includes cases where a restore HTTP response succeeds without
subsequent useful KV reuse, especially across restart or on hybrid/SWA checkpoint
paths. StateBraid does not treat an HTTP 200 as proof of compute rollback.

## Capability verdict

| Backend Contract v0.2 capability | Phase 8 llama.cpp verdict | Evidence / reason |
| --- | --- | --- |
| `namespace_isolation` | **unsupported** | current shared RAM prompt cache matches states by token longest-common-prefix and has no request trust namespace |
| `prefix_lookup` | **supported, execution-coupled** | actual served reusable prefix is reconstructed from `timings.cache_n` after a bounded completion probe |
| `admission_residency` | **unsupported as StateBraid authority** | llama.cpp owns slot selection, prompt-cache admission, eviction, and KV residency |
| `transactional_mutation` | **unsupported** | public slot save/restore/erase is not an exact transactional mutation facade |
| `rollback` | **unsupported** | no public all-or-nothing StateBraid mutation/rollback contract is claimed |
| `hit_attribution` | **supported** | `cache_n=N` attributes reuse to the exact first N prompt tokens supplied to the server |
| `generation_safety` | **supported** | audited exact reuse evaluates at least one prompt token (observed N-1); a backend may safely recompute more, but must never expose an empty generation input after full N-token reuse |

The resulting descriptor is intentionally `partial`: three declared capabilities,
four unsupported capabilities. This is a successful backend-neutrality result, not
an incomplete attempt to imitate the MLX managed-cache integration.

## Lookup semantics clarification

The second backend exposed a Phase 7 overfit: the original generation conformance
setup required a separately observable pre-safety exact hit. llama-server exposes
cache reuse only as execution-coupled factual timings, after generation safety has
already reduced or discarded the unsafe full exact reuse.

Backend Contract v0.2 therefore clarifies that a `LookupObservation` may be either
pre-execution or execution-coupled. It always describes the prefix actually
reusable/served by the backend. The generation-safety conformance requires a
non-empty prompt remainder after an exact-reuse setup: N-1 replay is valid, and a
larger safe recomputation is also valid. It does not demand an unsafe intermediate
state. The MLX managed adapter continues to pass the same contract.

## Trust-domain boundary

Current llama-server does not provide the equivalent of StateBraid's MLX
`cache_namespace`. Its shared `server_prompt_cache` can move a matching prompt
state between slots based on token prefix similarity. Therefore:

- the StateBraid llama.cpp HTTP adapter can only be constructed for
  `local-default`;
- any explicit non-default trust domain fails before a model request is sent;
- the resulting adapter accepts only its one server-global `local-default` cache
  identity; scheduler slot IDs are factual telemetry, not cache/trust identity;
- `namespace_isolation` is not declared;
- Phase 8 does not claim shared-server multi-tenant cache isolation.

For a security-sensitive multi-tenant deployment, use independently isolated
backend instances today or add a future upstream-supported trust namespace. Do not
use slot numbers as a substitute for a trust-domain primitive.

## Slot-ID boundary

The audited llama.cpp source wraps an out-of-range `id_slot` modulo the number of
slots. StateBraid does not inherit that ambiguity. Before each observation the
adapter reads `/slots` and requires the requested slot ID to exist exactly. It
refuses a value that would rely on upstream modulo wrapping.

This check is mechanical and does not make StateBraid the slot scheduler. llama.cpp
still owns slot scheduling, concurrency, and KV state.

## Conformance

The deterministic public-API fixture passes only the cases supported by the
three-capability descriptor:

- actual-prefix hit attribution: PASS;
- generation-safe exact reuse: PASS;
- namespace, stable/active residency, capacity, and rollback cases: explicit SKIP.

This demonstrates why Backend Contract v0.2 is graded: the same StateBraid
conformance framework can qualify a read/observe backend without falsely claiming
external cache-policy ownership.

## Real-runtime capability canary

The exact audited source was compiled locally with Apple Clang 21 using the CPU +
Accelerate backend (Metal disabled for this bounded compatibility check). The
canary used llama.cpp's own tiny server-test model
`ggml-org/models/tinyllamas/stories260K.gguf` (1.1 MiB; SHA256
`270cba1bd5109f42d03350f60406024560464db173c0e387d91f0426d3bd256d`) on one
temporary loopback-only slot with the shared RAM prompt cache disabled. No
production serving process was modified or restarted.

Observed public-API evidence:

| Step | Prompt tokens | `cache_n` / StateBraid matched prefix | Result |
| --- | ---: | ---: | --- |
| cold base prompt | 37 | 0 | no false hit |
| same-prefix extended prompt | 58 | 37 | exact 37-token prefix reuse |
| exact repeat of 58-token prompt | 58 | 57 | generation-safe N-1 reuse |

`GET /props` reported source commit `465e49b`; the compatibility probe therefore
returned `reference_source_match=true` and `reference_qualified=true`. The server
log independently showed the exact-repeat guard reducing `n_past` from 58 to 57
and evaluating one prompt token.

Two negative boundaries were exercised against the live server as well:

- construction for `trust_domain=tenant-a` failed closed before any model request;
- an unavailable `id_slot=3` failed closed instead of relying on llama.cpp's modulo
  slot wrapping.

This tiny-model canary qualifies the three declared Backend Contract v0.2 mechanics
for the exact audited llama.cpp source. It still does **not** qualify namespace
isolation, admission/residency authority, transactions, rollback, a production
model/cache profile, or v0.1 production runtime support.

## v0.1 support claim

Phase 8 does **not** widen `SUPPORTED_SCOPE_V0_1.md`. The v0.1 reference-qualified
runtime remains the exact MLX/Ornith profile. llama.cpp in Phase 8 is a Backend
Contract v0.2 capability qualification unless and until a later release explicitly
widens the production support matrix.
