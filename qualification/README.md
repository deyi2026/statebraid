# Qualification assets

This directory contains portable, source-controlled qualification inputs and
sanitized compact evidence for runtime profiles that are narrower than the
public v0.1 supported-runtime contract.

These assets are intentionally separate from raw research logs.  They must not
contain local absolute paths, credentials, process IDs, session IDs, opaque
runtime handles/epochs, full model reasoning, model weights, or large benchmark
payloads.

Qualification evidence does not widen `docs/SUPPORTED_SCOPE_V0_1.md` by itself.
Any support-matrix promotion still requires a separate protected decision and
the scope-widening gates documented there.

`determinism_audit.py` is the shared pre-gate for every reuse measurement:
identical greedy requests repeated N times must return bit-identical
completions on both the cold-prefill and the exact cache-replay path. The
runner scripts invoke it automatically as an abort-on-fail step 0 (pass
`--device-label metal|cpu` to bind the evidence to the execution device), so
a backend that fails it never reaches a reuse matrix or canary. The canary
output embeds the full audit result, including the server build_info.
`llama_cpp_hybrid_ssm/` holds the hybrid attention+SSM canary kit, where
prefix reuse silently changes meaning and stale or zeroed recurrent states
change answers without failing any timing check; it is qualified against the
pinned source build (commit 465e49b9c) with `runtime_qualified: true`.
