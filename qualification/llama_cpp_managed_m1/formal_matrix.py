#!/usr/bin/env python3
"""Portable real-GGUF managed-storage M1 mechanical matrix."""

from __future__ import annotations

import argparse
import json
import urllib.request
from typing import Any

from statebraid.adapters.llama_cpp_managed import (
    LLAMA_CPP_MANAGED_REFERENCE_SHA,
    LlamaCppManagedHTTPAdapter,
    LlamaCppStateBraidPromptCache,
)


def request_json(
    base_url: str, path: str, payload: dict[str, Any] | None = None, *, timeout: float = 120.0
) -> Any:
    body = None if payload is None else json.dumps(payload, separators=(",", ":")).encode()
    request = urllib.request.Request(
        base_url.rstrip("/") + path,
        data=body,
        headers={} if body is None else {"Content-Type": "application/json"},
        method="GET" if body is None else "POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode())


def tokenize(base_url: str, text: str) -> list[int]:
    return list(request_json(base_url, "/tokenize", {"content": text, "add_special": False})["tokens"])


def observation_dict(observation: Any) -> dict[str, int]:
    return {"cache_n": observation.matched_tokens, "prompt_n": len(observation.remaining)}


def run(base_url: str) -> dict[str, Any]:
    props = request_json(base_url, "/props")
    build_info = str(props["build_info"])
    source_prefix = build_info.rsplit("-", 1)[-1]
    if not LLAMA_CPP_MANAGED_REFERENCE_SHA.startswith(source_prefix):
        raise AssertionError(
            f"wrong managed source: build={build_info}, expected={LLAMA_CPP_MANAGED_REFERENCE_SHA}"
        )

    adapter = LlamaCppManagedHTTPAdapter(base_url, id_slot=0)
    cache = LlamaCppStateBraidPromptCache(adapter, max_sequences=3, max_bytes=2 * 1024**3)
    initial = dict(adapter.managed_store())
    if initial["n_handles"] != 0:
        raise AssertionError("formal matrix requires an empty initial managed store")

    stable = tokenize(
        base_url,
        "STATEBRAID FORMAL REAL GGUF STABLE PREFIX\n"
        + "mechanical stable prefix payload alpha beta gamma delta\n" * 48,
    )
    active1 = stable + tokenize(base_url, "ACTIVE SUCCESSOR ONE epsilon zeta eta theta\n" * 8)
    active2 = active1 + tokenize(base_url, "ACTIVE SUCCESSOR TWO iota kappa lambda mu\n" * 8)
    unrelated = tokenize(
        base_url,
        "UNRELATED SESSION OMEGA\n" + "independent prompt with no shared StateBraid prefix\n" * 40,
    )

    cold = cache.lookup(cache.namespace, stable)
    if cold.matched_tokens != 0:
        raise AssertionError("stable seed must be cold")
    stable_state = cache.capture_current(stable)
    if not cache.admit_captured(stable, stable_state, role="stable"):
        raise AssertionError("stable admission rejected")

    ext1 = cache.lookup(cache.namespace, active1)
    if ext1.matched_tokens != len(stable):
        raise AssertionError("active1 did not restore the exact stable prefix")
    active1_state = cache.capture_current(active1)
    if not cache.admit_captured(active1, active1_state, role="active"):
        raise AssertionError("active1 admission rejected")

    ext2 = cache.lookup(cache.namespace, active2)
    if ext2.matched_tokens != len(active1):
        raise AssertionError("active2 did not restore the exact active1 prefix")
    active2_state = cache.capture_current(active2)
    if not cache.admit_captured(active2, active2_state, role="active", predecessor_tokens=active1):
        raise AssertionError("active2 successor admission rejected")

    after_successor = dict(adapter.managed_store())
    successor_stats = cache.activation_stats()
    if successor_stats["active_successor_evictions"] != 1 or after_successor["n_handles"] != 2:
        raise AssertionError("active successor did not converge to stable + newest active")

    interleave = cache.lookup(cache.namespace, unrelated)
    if interleave.matched_tokens != 0:
        raise AssertionError("unrelated session unexpectedly reused managed state")

    returned = cache.generation_safe_exact(cache.namespace, active2)
    if not 0 < returned.matched_tokens < len(active2):
        raise AssertionError("exact return did not preserve non-empty generation-safe replay")

    if not cache.trim_to(n_sequences=1):
        raise AssertionError("trim_to(n_sequences=1) failed")
    cache.backend.assert_physical_matches_registry()
    after_trim = dict(adapter.managed_store())
    trim_stats = cache.activation_stats()

    checks = {
        "stable_cold": cold.matched_tokens == 0,
        "stable_to_active1_exact": ext1.matched_tokens == len(stable),
        "active1_to_active2_exact": ext2.matched_tokens == len(active1),
        "active_successor_evicted": successor_stats["active_successor_evictions"] == 1,
        "interleave_cold": interleave.matched_tokens == 0,
        "return_active2_generation_safe": 0 < returned.matched_tokens < len(active2),
        "trim_physical_logical_one": after_trim["n_handles"] == trim_stats["n_sequences"] == 1,
        "trim_payload_bytes_match": after_trim["n_bytes"] == trim_stats["n_bytes"],
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "build_info": build_info,
        "managed_reference_sha": LLAMA_CPP_MANAGED_REFERENCE_SHA,
        "token_lengths": {
            "stable": len(stable),
            "active1": len(active1),
            "active2": len(active2),
            "unrelated": len(unrelated),
        },
        "cold_stable": observation_dict(cold),
        "active1_extension": observation_dict(ext1),
        "active2_extension": observation_dict(ext2),
        "interleave": observation_dict(interleave),
        "return_active2": observation_dict(returned),
        "stats_after_successor": successor_stats,
        "stats_after_trim": trim_stats,
        "checks": checks,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8901")
    args = parser.parse_args()
    result = run(args.base_url)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    raise SystemExit(0 if result["status"] == "PASS" else 2)


if __name__ == "__main__":
    main()
