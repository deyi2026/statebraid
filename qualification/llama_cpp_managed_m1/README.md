# llama.cpp managed-storage M1 qualification kit

This kit targets the exact experimental M1 source identity in `manifest.json`
and the frozen patch distributed by StateBraid. M1 remains
`runtime_qualified=false`.

With the exact managed llama-server already running on loopback and with an
empty managed store, run the mechanical and Agent gates serially:

```text
PYTHONPATH=src python qualification/determinism_audit.py \
  --base-url http://127.0.0.1:8901

PYTHONPATH=src python qualification/llama_cpp_managed_m1/formal_matrix.py \
  --base-url http://127.0.0.1:8901

PYTHONPATH=src python qualification/llama_cpp_managed_m1/agent_canary.py \
  --base-url http://127.0.0.1:8901 \
  --model qwen3.6-35b-a3b-pruned-v2

PYTHONPATH=src python qualification/llama_cpp_managed_m1/memory_pressure.py \
  --base-url http://127.0.0.1:8901
```

Passing `--pid <server-pid>` to `memory_pressure.py` additionally enables the
OS footprint/RSS observation gates. The logical sequence/byte and injected
physical-GC-failure gates do not require a PID.

Restart qualification is deliberately two-step so no server control is hidden
inside the runner:

```text
PYTHONPATH=src python qualification/llama_cpp_managed_m1/restart_probe.py prepare \
  --base-url http://127.0.0.1:8901 --state-file /tmp/statebraid-m1-restart.json

# Stop the server completely and restart the same exact M1 build.

PYTHONPATH=src python qualification/llama_cpp_managed_m1/restart_probe.py verify \
  --base-url http://127.0.0.1:8901 --state-file /tmp/statebraid-m1-restart.json
```

The transient state file contains an opaque old-process handle only long enough
to prove restart invalidation. It is not a repository artifact and must not be
committed. The verify step requires a new epoch, an empty post-restart store and
HTTP 400 rejection of the stale restore.

`compact_evidence.json` preserves the prior formal Agent, stable/active,
memory-pressure/GC-failure and restart verdicts without raw reasoning,
process/session identifiers, opaque handles/epochs or local filesystem paths.
