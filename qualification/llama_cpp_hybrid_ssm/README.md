# llama.cpp hybrid attention+SSM qualification kit (candidate)

A canary-grade extension of the mechanical reuse checks to hybrid
attention+SSM backends. Motivated by a real hybrid-SSM serving incident where
prefix-cache slot indexing used the KV block size in place of the
recurrent-state block size: prefix hits then read out-of-bounds all-zero SSM
states and the server kept answering, silently wrong. Hybrid backends are
exactly where "prefix reuse" silently changes meaning, so they get:

1. `qualification/determinism_audit.py` first - identical greedy requests
   repeated N times must be bit-identical, on the cold path and on the exact
   cache-replay path. A backend that cannot pass this has no business being
   measured by any reuse matrix.
2. `mechanical_canary.py` - the stock mechanical reuse-bound checks plus
   generation-content identity: the exact replay and A-after-B generations must
   reproduce the cold reference content bit-identically. A zeroed or stale SSM
   state does not fail timing checks; it changes the answer.

Run with any llama.cpp-supported hybrid GGUF (falcon-h1, granite-4.0-h, jamba,
qwen3-next, ...). The recorded evidence below used a small falcon-h1 model on a
stock distribution build. Update `manifest.json` whenever the build or model
changes. This kit is candidate-grade: it does not widen the v0.1
supported-runtime matrix and `runtime_qualified` stays false until the checks
are rerun against the exact pinned source build.

## Run

```text
llama-server -m <hybrid-model>.gguf --host 127.0.0.1 --port 8902 --parallel 1 \
  -c 8192 -ngl 999 --no-webui --slots --slot-save-path <scratch-dir>

PYTHONPATH=src python qualification/determinism_audit.py \
  --base-url http://127.0.0.1:8902 --repeats 4

PYTHONPATH=src python qualification/llama_cpp_hybrid_ssm/mechanical_canary.py \
  --base-url http://127.0.0.1:8902
```

Both exit 0 on PASS and 2 on FAIL. On hybrid backends expect divergence reuse
to stop at the last recurrent-state snapshot, which can be far below the true
token LCP; the canary checks reuse never exceeds the true LCP, and records the
observed truncation point.
