# Stock llama.cpp + real GGUF qualification kit

This kit reproduces the narrow Apple L1 mechanical qualification candidate for
the exact source/model identity in `manifest.json`.  It does not download or
ship model weights and does not widen the v0.1 supported-runtime matrix.

With an exact single-slot llama-server already running on loopback:

```text
PYTHONPATH=src python qualification/llama_cpp_real_gguf/mechanical_canary.py \
  --base-url http://127.0.0.1:8901

PYTHONPATH=src python qualification/llama_cpp_real_gguf/adapter_boundaries.py \
  --base-url http://127.0.0.1:8901
```

The mechanical canary checks cold/exact generation safety, prefix extension,
divergence, A-B-A stale-suffix safety, multi-turn extension and slot erase. The
boundary canary verifies that a non-default trust domain and an invalid slot are
rejected before a cache-bearing completion can be misrepresented.

`compact_evidence.json` records only the previously verified mechanical facts
and SHA256 provenance of the original research artifacts. Raw logs and model
reasoning are deliberately not copied into this repository.
