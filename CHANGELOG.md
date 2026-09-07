# Changelog

All notable StateBraid changes are recorded here. Version strings follow PEP 440;
release tags use the same version prefixed with `v`.

## Unreleased

No unreleased user-facing changes are recorded yet.

## 0.1.0rc1 - 2026-09-07

### Backend contract

- add the second backend proof against exact upstream llama.cpp `465e49b9`: a
  public-HTTP partial adapter that observes `cache_n`, validates exact slot IDs,
  fails closed on non-default trust domains, and preserves llama.cpp ownership of
  scheduling/KV storage;
- distinguish llama.cpp public-API compatibility from exact audited source-commit
  qualification via `/props` build metadata;
- clarify that Backend Contract v0.2 lookup evidence may be execution-coupled and
  remove the MLX-shaped requirement to expose an unsafe pre-replay exact hit;
- add Backend Contract v0.2 with graded capability declarations and dependency
  validation;
- add reusable backend conformance for namespace isolation, actual-prefix hits,
  stable/active residency, capacity, rollback, and generation-safe exact reuse;
- declare and qualify the existing MLX adapter against the new mechanical suite
  without widening the narrower v0.1 runtime support scope;
- make MLX compatibility probing fail closed on import-time backend exceptions.


This is the first release-candidate metadata state. It is **not** a public final
release and this preparation phase does not create a Git tag or GitHub Release.

### Added

- backend-neutral Compute Contract v0.1 for exact cache identity, stable/active
  lineage, bounded residency, transactional rollback, generation-safe reuse and
  factual compute telemetry;
- MLX transactional-storage adapter and a SHA256-frozen reference integration
  patch against exact upstream `mlx-lm` base
  `6d21ce4b065a2e163fa6de76a9936c61aeb5784a`;
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
- project source distribution is licensed under Apache License 2.0 and retains the separate
  Apple/mlx-lm MIT notice required by the reference-integration provenance.

### Qualification boundary

The v0.1 real serving qualification remains intentionally narrower than the core
API. See `docs/SUPPORTED_SCOPE_V0_1.md` for the exact Apple Silicon/macOS,
MLX-LM, Ornith, cache-shape, concurrency and trust-domain limits.
