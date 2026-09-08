# Changelog

All notable StateBraid changes are recorded here. Version strings follow PEP 440;
release tags use the same version prefixed with `v`.

## Unreleased

No unreleased user-facing changes are recorded yet.

## 0.1.0 - 2026-09-07

### Public distribution hygiene

- make repository-file links in the packaged README absolute GitHub URLs so the
  PyPI long description does not emit broken relative documentation links;
- add an explicit private GitHub Security Advisory reporting path and publish
  documentation/security project URLs in package metadata;
- require the exact patched MLX-LM checkout to be installed, with its declared
  dependencies, in the serving environment before `statebraid-doctor mlx` is
  treated as a compatibility gate;
- add release-checklist gates for public-ref/history privacy, portable links,
  vulnerability reporting, and remote-branch minimization before visibility is
  changed from private to public.

### Harness integration boundary

- add Harness ↔ StateBraid Integration Contract v0.1 with a closed mechanical
  input/output schema and explicit rejection of task/evidence/checkpoint/tool/
  completion/fold/retry semantics and legacy `cache_tag` authority;
- keep backend/model selection outside StateBraid and add only a mechanical
  compatibility check for a backend selected by the Harness/gateway;
- retain trusted ownership→opaque trust-domain derivation as a library primitive,
  while explicitly rejecting the experimental generic Phase 9 chat/router/proxy
  service as a StateBraid product surface;
- require backend reuse observers to publish passive vs execution-coupled mode and
  backend-state mutation risk, and require generation-safety claims to carry a
  narrow qualification profile.

### Backend contract

- add the second backend proof against exact upstream llama.cpp `465e49b9`: a
  public-HTTP partial adapter that observes `cache_n`, validates exact slot IDs,
  fails closed on non-default trust domains, and preserves llama.cpp ownership of
  scheduling/KV storage;
- bind both llama.cpp doctor and direct execution adapter to the exact audited
  source commit via `/props`, and require `/props.total_slots` to agree with the
  concrete `/slots` surface before any completion probe;
- clarify that Backend Contract v0.2 lookup evidence may be execution-coupled and
  remove the MLX-shaped requirement to expose an unsafe pre-replay exact hit;
- add Backend Contract v0.2 with graded capability declarations and dependency
  validation;
- add reusable backend conformance for namespace isolation, actual-prefix hits,
  stable/active residency, capacity, rollback, and generation-safe exact reuse;
- declare and qualify the existing MLX adapter against the new mechanical suite
  without widening the narrower v0.1 runtime support scope;
- make MLX compatibility probing fail closed on import-time backend exceptions.


This is the first StateBraid v0.1 release line. Advancing distribution metadata to
`0.1.0` does not widen Compute Contract v0.1, Supported Scope v0.1, or any backend
runtime qualification; tag and release creation remain separate protected gates.

### Added

- backend-neutral Compute Contract v0.1 for exact cache identity, stable/active
  lineage, bounded residency, transactional rollback, generation-safe reuse and
  factual compute telemetry;
- MLX transactional-storage adapter and a SHA256-frozen reference integration
  patch against exact upstream `mlx-lm` base
  `7fb4be44d560e5b74595210f83cb6003a57e52a7`;
- request-scoped trust-domain cache namespaces with exact cross-domain isolation;
- `statebraid-doctor` capability/scope diagnostics and `statebraid-reference`
  reference-patch export tooling;
- machine-readable v0.1 supported-scope metadata;
- zero-model GitHub Actions gates for Python 3.11-3.14, Pyright, contracts,
  privacy and package contents.

### Changed

- product scope narrowed to **agent-aware compute continuity**; task, evidence,
  execution and provider-interruption semantics remain agent-harness/model owned;
- StateBraid activation remains explicit and default-off;
- the exact qualified MLX reference moved to upstream `7fb4be44...` plus the
  requalified StateBraid patch after strict-serial real-model parity; Supported
  Scope v0.1 remains the same narrow Apple/Ornith/batch/unquantized/1x1 profile;
- project source distribution is licensed under Apache License 2.0 and retains the separate
  Apple/mlx-lm MIT notice required by the reference-integration provenance.

### Qualification boundary

The v0.1 real serving qualification remains intentionally narrower than the core
API. See `docs/SUPPORTED_SCOPE_V0_1.md` for the exact Apple Silicon/macOS,
MLX-LM, Ornith, cache-shape, concurrency and trust-domain limits.

Historical real-model LFL StateBraid ON/OFF evidence remains bound to immutable
LFL snapshot `5c8e8bc3344f27a2a2586d2e65c4a317353089a3`. Current committed LFL main
`22039c087adcdd60f0beb6f68848a3258e4262b5` passed deterministic/static
requalification after its six Harness durability commits; a current-main
real-model StateBraid ON/OFF A/B was **not rerun**. The LFL live dirty worktree is
outside that qualification.
