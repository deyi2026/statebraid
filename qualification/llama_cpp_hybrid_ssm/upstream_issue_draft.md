# Upstream draft: hybrid attention+SSM prompt-cache reuse truncates at the last recurrent-state snapshot

Proposed target: llama.cpp issue tracker (server). Status: draft, not yet filed.

## Title

llama-server: on hybrid attention+SSM models, cache reuse after prompt
divergence truncates at the last recurrent-state snapshot, far below the
true token LCP - document or expose the effective reuse boundary

## Environment

- llama.cpp b-465e49b9c (0.4.0-dev, source build) and stock 0.3.0
  (build 10621, commit c1d0e7a00)
- macOS arm64; reproduced on both Metal and CPU backends
- model: Falcon-H1-0.5B-Instruct Q4_K_M (hybrid attention + SSM)
- server flags: `--parallel 1 -c 8192 -ngl 999 --no-webui --slots`
  (and `-ngl 0` for the CPU tier)

## Reproduction

Single slot; send prompt A, then prompt B, where A and B share a
1065-token common prefix and diverge afterwards (true token LCP = 1059).
Observe `timings.n_cache_reuse` on the second, diverging request via
non-stream `/completion`.

## Observed

- Second request reports `cache_n = 553`, `prompt_n = 516`, consistently.
- The reused length corresponds to the most recent recurrent-state
  snapshot boundary, not the true token LCP (1059).
- Identical numbers across two builds and both devices (Metal/CPU):
  upstream, device-independent behavior, not a distribution patch or a
  Metal-specific kernel issue.

## Correctness impact

None observed, and that is the point:

- greedy determinism audit passes (4x cold, 4x cache-replay, bit-identical);
- exact-prefix replay reproduces the cold generation bit-identically;
- A-after-divergent-B reproduces the cold reference content as well.

The truncation is conservative and mechanically safe.

## Why it still matters

`cache_n` on hybrid backends measures snapshot-aligned reuse, while on
attention-only models it tracks the token prefix (up to block
granularity). Any accounting, benchmark, or autoscaling logic that reads
`cache_n` as "tokens of common prefix reused" will over-report effective
reuse on hybrid architectures. We hit this while qualifying a
prefix-reuse cache controller: predicted reuse 1059, actual 553.

## Ask

Either document per-backend `cache_n` semantics for hybrid models
(recurrent-state snapshot granularity, may be far below the token LCP),
or expose the effective reuse boundary explicitly so callers can
distinguish token-prefix reuse from snapshot-aligned reuse.
