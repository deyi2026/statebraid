#!/usr/bin/env python3
"""Portable logical-byte-pressure and physical-GC-failure qualification runner."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
import urllib.request
from typing import Any

from statebraid.adapters.llama_cpp_managed import (
    LLAMA_CPP_MANAGED_REFERENCE_SHA,
    LlamaCppManagedHTTPAdapter,
    LlamaCppStateBraidPromptCache,
)


MAX_SEQUENCES = 2
MAX_BYTES = 512 * 1024 * 1024
CYCLES = 4


def request_json(
    base_url: str, path: str, payload: dict[str, Any] | None = None, *, timeout: float = 180.0
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


def footprint_mib(pid: int | None) -> float | None:
    if pid is None:
        return None
    try:
        process = subprocess.run(
            ["/usr/bin/footprint", str(pid)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=30,
        )
    except Exception:
        return None
    match = re.search(r"Footprint:\s*([0-9.]+)\s*(KB|MB|GB)", process.stdout)
    if not match:
        return None
    value = float(match.group(1))
    unit = match.group(2)
    return value / 1024.0 if unit == "KB" else value * 1024.0 if unit == "GB" else value


def rss_mib(pid: int | None) -> float | None:
    if pid is None:
        return None
    try:
        output = subprocess.check_output(["ps", "-o", "rss=", "-p", str(pid)], text=True).strip()
        return int(output) / 1024.0 if output else None
    except Exception:
        return None


def sample(adapter: LlamaCppManagedHTTPAdapter, label: str, pid: int | None) -> dict[str, Any]:
    store = dict(adapter.managed_store())
    return {
        "label": label,
        "store_n_handles": store["n_handles"],
        "store_n_tokens": store["n_tokens"],
        "store_n_bytes": store["n_bytes"],
        "footprint_mib": footprint_mib(pid),
        "rss_mib": rss_mib(pid),
    }


def require_budget(cache: LlamaCppStateBraidPromptCache) -> dict[str, Any]:
    stats = cache.activation_stats()
    if int(stats["n_sequences"]) > MAX_SEQUENCES or int(stats["n_bytes"]) > MAX_BYTES:
        raise AssertionError("managed logical budget exceeded")
    if int(stats["pending_drops"]) != 0:
        raise AssertionError("unexpected pending physical drop")
    cache.backend.assert_physical_matches_registry()
    return stats


def run_cycle(
    base_url: str,
    cache: LlamaCppStateBraidPromptCache,
    adapter: LlamaCppManagedHTTPAdapter,
    cycle: int,
    pid: int | None,
) -> dict[str, Any]:
    stable = tokenize(
        base_url,
        "STATEBRAID MEMORY PRESSURE STABLE PREFIX\n"
        + "mechanical stable payload for allocator reuse qualification\n" * 72,
    )
    active1 = stable + tokenize(base_url, "ACTIVE SUCCESSOR ONE\n" + "alpha extension\n" * 24)
    active2 = active1 + tokenize(base_url, "ACTIVE SUCCESSOR TWO\n" + "beta extension\n" * 24)
    active3 = active2 + tokenize(base_url, "ACTIVE SUCCESSOR THREE\n" + "gamma extension\n" * 24)

    pre = sample(adapter, f"cycle{cycle}_pre", pid)
    cold = cache.lookup(cache.namespace, stable)
    if cold.matched_tokens != 0 or not cache.capture_and_admit(stable, role="stable"):
        raise AssertionError("stable seed/admission failed")
    stable_stats = require_budget(cache)
    one = cache.lookup(cache.namespace, active1)
    if one.matched_tokens != len(stable) or not cache.capture_and_admit(active1, role="active"):
        raise AssertionError("active1 reuse/admission failed")
    one_stats = require_budget(cache)
    two = cache.lookup(cache.namespace, active2)
    if two.matched_tokens != len(active1) or not cache.capture_and_admit(active2, role="active", predecessor_tokens=active1):
        raise AssertionError("active2 reuse/admission failed")
    two_stats = require_budget(cache)
    three = cache.lookup(cache.namespace, active3)
    if three.matched_tokens != len(active2) or not cache.capture_and_admit(active3, role="active", predecessor_tokens=active2):
        raise AssertionError("active3 reuse/admission failed")
    three_stats = require_budget(cache)

    live = sample(adapter, f"cycle{cycle}_live", pid)
    if not cache.trim_to(n_sequences=0, n_bytes=0):
        raise AssertionError("trim to empty failed")
    cache.backend.assert_physical_matches_registry()
    adapter.clear_live_slot()
    time.sleep(0.6)
    post = sample(adapter, f"cycle{cycle}_post", pid)
    if post["store_n_handles"] != 0 or post["store_n_bytes"] != 0:
        raise AssertionError("physical store not empty after churn cycle")

    return {
        "cycle": cycle,
        "token_lengths": {
            "stable": len(stable),
            "active1": len(active1),
            "active2": len(active2),
            "active3": len(active3),
        },
        "reuse": {
            "cold": [cold.matched_tokens, len(cold.remaining)],
            "stable_to_active1": [one.matched_tokens, len(one.remaining)],
            "active1_to_active2": [two.matched_tokens, len(two.remaining)],
            "active2_to_active3": [three.matched_tokens, len(three.remaining)],
        },
        "stats": {"stable": stable_stats, "active1": one_stats, "active2": two_stats, "active3": three_stats},
        "samples": {"pre": pre, "live": live, "post": post},
    }


def gc_failure_gate(base_url: str, adapter: LlamaCppManagedHTTPAdapter) -> dict[str, Any]:
    cache = LlamaCppStateBraidPromptCache(adapter, max_sequences=2, max_bytes=MAX_BYTES)
    stable = tokenize(base_url, "GC FAILURE STABLE\n" + "stable\n" * 80)
    active1 = stable + tokenize(base_url, "GC ACTIVE ONE\n" + "one\n" * 40)
    active2 = active1 + tokenize(base_url, "GC ACTIVE TWO\n" + "two\n" * 40)
    extra = active2 + tokenize(base_url, "GC EXTRA MUST NOT CAPTURE\n" + "extra\n" * 20)

    cache.lookup(cache.namespace, stable)
    if not cache.capture_and_admit(stable, role="stable"):
        raise AssertionError("gc stable admission rejected")
    cache.lookup(cache.namespace, active1)
    if not cache.capture_and_admit(active1, role="active"):
        raise AssertionError("gc active1 admission rejected")
    cache.lookup(cache.namespace, active2)
    active2_state = cache.capture_current(active2)
    active1_handle = next(state.handle for key, state in cache.backend.records.items() if key.tokens == tuple(active1))
    original_drop = adapter.drop_state

    def fail_old_active(state: Any) -> None:
        if state.handle == active1_handle:
            raise RuntimeError("injected physical GC failure")
        original_drop(state)

    adapter.drop_state = fail_old_active  # type: ignore[method-assign]
    admit_error = None
    try:
        cache.admit_captured(active2, active2_state, role="active", predecessor_tokens=active1)
    except RuntimeError as exc:
        admit_error = str(exc)
    if admit_error != "injected physical GC failure":
        raise AssertionError("expected injected GC failure")

    pending = cache.activation_stats()
    store_after_failure = dict(adapter.managed_store())
    before_blocked = int(store_after_failure["n_handles"])
    blocked_error = None
    try:
        cache.capture_current(extra)
    except RuntimeError as exc:
        blocked_error = str(exc)
    after_blocked = dict(adapter.managed_store())
    if blocked_error != "injected physical GC failure" or int(after_blocked["n_handles"]) != before_blocked:
        raise AssertionError("unresolved cleanup did not block new capture")

    adapter.drop_state = original_drop  # type: ignore[method-assign]
    cache.backend.flush_drops()
    cache.backend.assert_physical_matches_registry()
    if not cache.trim_to(n_sequences=0, n_bytes=0):
        raise AssertionError("gc gate cleanup trim failed")
    adapter.clear_live_slot()
    final = dict(adapter.managed_store())
    checks = {
        "pending_cleanup_visible": int(pending["pending_drops"]) == 1,
        "new_capture_blocked": blocked_error == "injected physical GC failure",
        "no_new_remote_handle": int(after_blocked["n_handles"]) == before_blocked,
        "reconciled": final["n_handles"] == 0 and final["n_bytes"] == 0,
    }
    return {"checks": checks, "final_store": {"n_handles": final["n_handles"], "n_bytes": final["n_bytes"]}}


def run(base_url: str, pid: int | None) -> dict[str, Any]:
    props = request_json(base_url, "/props")
    build_info = str(props.get("build_info", ""))
    reference_source_exact = LLAMA_CPP_MANAGED_REFERENCE_SHA.startswith(build_info.rsplit("-", 1)[-1])
    if not reference_source_exact:
        raise AssertionError("wrong managed source")
    adapter = LlamaCppManagedHTTPAdapter(base_url, id_slot=0)
    if int(adapter.managed_store()["n_handles"]) != 0:
        raise AssertionError("memory-pressure run requires an empty initial managed store")

    baseline = sample(adapter, "baseline", pid)
    cache = LlamaCppStateBraidPromptCache(adapter, max_sequences=MAX_SEQUENCES, max_bytes=MAX_BYTES)
    cycles = [run_cycle(base_url, cache, adapter, index, pid) for index in range(1, CYCLES + 1)]
    post_footprints = [cycle["samples"]["post"]["footprint_mib"] for cycle in cycles]
    live_footprints = [cycle["samples"]["live"]["footprint_mib"] for cycle in cycles]
    payload_mib = max(cycle["samples"]["live"]["store_n_bytes"] for cycle in cycles) / (1024 * 1024)
    footprint_available = all(value is not None for value in post_footprints + live_footprints)
    post_growth = None
    footprint_gate = None
    if footprint_available:
        values = [float(value) for value in post_footprints]
        post_growth = values[-1] - values[0]
        footprint_gate = post_growth < payload_mib

    gc_gate = gc_failure_gate(base_url, adapter)
    final = sample(adapter, "final", pid)
    logical_ok = all(
        int(stats["n_sequences"]) <= MAX_SEQUENCES and int(stats["n_bytes"]) <= MAX_BYTES
        for cycle in cycles
        for stats in cycle["stats"].values()
    )
    physical_empty = all(cycle["samples"]["post"]["store_n_handles"] == 0 for cycle in cycles)
    checks = {
        "exact_reference_source": reference_source_exact,
        "logical_sequence_and_byte_budget_always_respected": logical_ok,
        "physical_store_empty_after_every_churn_cycle": physical_empty,
        "gc_failure_blocks_new_capture": all(gc_gate["checks"].values()),
        "final_store_empty": final["store_n_handles"] == 0 and final["store_n_bytes"] == 0,
    }
    if pid is not None:
        checks["footprint_observed"] = footprint_available
        checks["post_drop_footprint_did_not_accumulate_one_live_working_set"] = footprint_gate is True

    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "build_info": build_info,
        "managed_reference_sha": LLAMA_CPP_MANAGED_REFERENCE_SHA,
        "max_sequences": MAX_SEQUENCES,
        "max_bytes": MAX_BYTES,
        "cycles": cycles,
        "footprint_analysis": {
            "observed": footprint_available,
            "post_drop_footprint_mib": post_footprints,
            "live_footprint_mib": live_footprints,
            "max_live_payload_mib": payload_mib,
            "post_drop_growth_first_to_last_mib": post_growth,
        },
        "gc_failure_gate": gc_gate,
        "final": final,
        "checks": checks,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8901")
    parser.add_argument("--pid", type=int, help="optional server PID; enables OS footprint/RSS gates")
    args = parser.parse_args()
    result = run(args.base_url, args.pid)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    raise SystemExit(0 if result["status"] == "PASS" else 2)


if __name__ == "__main__":
    main()
