#!/usr/bin/env python3
"""E1 extension of determinism_audit.py: cold/cache x single/neighbor 2x2 matrix.

Extends the base greedy-determinism audit (qualification pre-gate) per review
book 7.1: separate the cold-prefill path from the exact cache-replay path, and
within each compare a lone request against a request that runs while a
neighbor occupies another slot, so that general batch-composition drift can be
distinguished from cache-recovery-specific changes.

Arms (the probe is one fixed greedy request pinned to id_slot=0):
  A1 cold-single:     erase -> probe(cache_prompt=False), repeated
  A2 cold-neighbor:   erase -> neighbor starts on id_slot=1 (different prompt,
                      cache_prompt=False, longer n_predict) -> probe(cache_prompt=False)
  A3 cached-single:   erase -> prime probe(cache_prompt=True) -> repeated probe(cache_prompt=True), no erase between
  A4 cached-neighbor: repeated { erase -> prime -> neighbor starts -> probe(cache_prompt=True) }

Gating checks (identical semantics to the base audit):
  cold_repeat_identical, cached_repeat_identical, replay_matches_cold, generation_nonempty

Non-gating observations (no pre-registered direction; identical or divergent
outputs are both valid findings, per review book 7.1):
  neighbor_cold_matches_cold_single, neighbor_cached_matches_cached_single,
  neighbor_cached_matches_cold, neighbor_generations_nonempty

Requires the server to expose the slot erase endpoint (--slot-save-path set;
GET /slots additionally needs --slots). The audit erases slots: run it against
an isolated port, never the production 8901.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import threading
import time
import urllib.error
import urllib.request
from typing import Any

PROBE_PROMPT = (
    "StateBraid determinism audit fixture. This text is intentionally stable and mechanical. "
    "The backend must return bit-identical completions for identical greedy requests. "
) * 24 + "\nRepeat one short deterministic sentence about the weather on a calm morning."

NEIGHBOR_PROMPT = (
    "StateBraid determinism audit neighbor fixture. This neighbor text shares no reuse intent "
    "with the probe; it occupies a different slot and only changes batch composition. "
) * 20 + "\nList three mechanical facts about a quiet harbor at dawn."


def request_json(
    base_url: str, path: str, payload: dict[str, Any] | None = None, *, timeout: float = 300.0
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


def completion(
    base_url: str,
    tokens: list[int],
    *,
    id_slot: int,
    cache_prompt: bool,
    n_predict: int,
    seed: int,
) -> dict[str, Any]:
    return dict(
        request_json(
            base_url,
            "/completion",
            {
                "prompt": tokens,
                "id_slot": id_slot,
                "cache_prompt": cache_prompt,
                "n_cache_reuse": 0,
                "n_predict": n_predict,
                "stream": False,
                "temperature": 0,
                "seed": seed,
            },
        )
    )


def erase(base_url: str, id_slot: int = 0) -> None:
    request_json(base_url, "/slots/%d?action=erase" % id_slot, {})


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def summarize(response: dict[str, Any], wall_s: float) -> dict[str, Any]:
    content = str(response.get("content", ""))
    timings = response.get("timings") or {}
    usage = response.get("usage") or {}
    return {
        "content_sha256": digest(content),
        "content_chars": len(content),
        "stop_type": str(response.get("stop_type")),
        "wall_s": round(wall_s, 3),
        "prompt_n": timings.get("prompt_n", usage.get("prompt_tokens")),
        "predicted_n": timings.get("predicted_n", usage.get("completion_tokens")),
        "cached_n": timings.get("cached_n"),
    }


def run_probe(base_url: str, tokens: list[int], *, cache_prompt: bool, n_predict: int, seed: int) -> dict[str, Any]:
    t0 = time.monotonic()
    response = completion(base_url, tokens, id_slot=0, cache_prompt=cache_prompt, n_predict=n_predict, seed=seed)
    return summarize(response, time.monotonic() - t0)


def run_neighbor(
    base_url: str, tokens: list[int], *, n_predict: int, seed: int, out: dict[str, Any]
) -> None:
    t0 = time.monotonic()
    try:
        response = completion(base_url, tokens, id_slot=1, cache_prompt=False, n_predict=n_predict, seed=seed)
        out["neighbor"] = summarize(response, time.monotonic() - t0)
    except Exception as exc:  # noqa: BLE001 - recorded, not raised
        out["neighbor"] = {"error": repr(exc)}


def run(
    base_url: str,
    repeats: int,
    n_predict: int,
    neighbor_n_predict: int,
    seed: int,
    neighbor_lead_s: float,
    device_label: str,
) -> dict[str, Any]:
    props = request_json(base_url, "/props")
    build_info = str(props.get("build_info", ""))

    probe_tokens = tokenize(base_url, PROBE_PROMPT)
    neighbor_tokens = tokenize(base_url, NEIGHBOR_PROMPT)

    # erase endpoint sanity (distinct failure mode: 501 without --slot-save-path)
    erase(base_url, 0)
    erase(base_url, 1)

    # A1 cold-single
    a1: list[dict[str, Any]] = []
    for _ in range(repeats):
        erase(base_url, 0)
        a1.append(run_probe(base_url, probe_tokens, cache_prompt=False, n_predict=n_predict, seed=seed))

    # A2 cold-neighbor
    a2: list[dict[str, Any]] = []
    a2_neighbors: list[dict[str, Any]] = []
    for _ in range(repeats):
        erase(base_url, 0)
        erase(base_url, 1)
        holder: dict[str, Any] = {}
        thread = threading.Thread(
            target=run_neighbor,
            args=(base_url, neighbor_tokens),
            kwargs={"n_predict": neighbor_n_predict, "seed": seed, "out": holder},
        )
        thread.start()
        time.sleep(neighbor_lead_s)
        a2.append(run_probe(base_url, probe_tokens, cache_prompt=False, n_predict=n_predict, seed=seed))
        thread.join()
        a2_neighbors.append(holder.get("neighbor"))

    # A3 cached-single: prime then repeat on the cached prefix
    erase(base_url, 0)
    prime = run_probe(base_url, probe_tokens, cache_prompt=True, n_predict=n_predict, seed=seed)
    a3: list[dict[str, Any]] = []
    for _ in range(repeats):
        a3.append(run_probe(base_url, probe_tokens, cache_prompt=True, n_predict=n_predict, seed=seed))

    # A4 cached-neighbor: per repeat re-prime so the cached path is unambiguous
    a4: list[dict[str, Any]] = []
    a4_neighbors: list[dict[str, Any]] = []
    a4_primes: list[dict[str, Any]] = []
    for _ in range(repeats):
        erase(base_url, 0)
        erase(base_url, 1)
        a4_primes.append(run_probe(base_url, probe_tokens, cache_prompt=True, n_predict=n_predict, seed=seed))
        holder: dict[str, Any] = {}
        thread = threading.Thread(
            target=run_neighbor,
            args=(base_url, neighbor_tokens),
            kwargs={"n_predict": neighbor_n_predict, "seed": seed, "out": holder},
        )
        thread.start()
        time.sleep(neighbor_lead_s)
        a4.append(run_probe(base_url, probe_tokens, cache_prompt=True, n_predict=n_predict, seed=seed))
        thread.join()
        a4_neighbors.append(holder.get("neighbor"))

    cold_ref = a1[0]["content_sha256"] if a1 else ""
    cached_ref = a3[0]["content_sha256"] if a3 else ""

    checks = {
        "cold_repeat_identical": len({r["content_sha256"] for r in a1}) == 1,
        "cached_repeat_identical": len({r["content_sha256"] for r in a3}) == 1,
        "replay_matches_cold": cold_ref == cached_ref,
        "generation_nonempty": all(r["content_chars"] > 0 for r in a1),
    }
    neighbor_digests = [n.get("content_sha256") for n in (a2_neighbors + a4_neighbors) if n and "error" not in n]
    observations = {
        "neighbor_cold_matches_cold_single": all(r["content_sha256"] == cold_ref for r in a2),
        "neighbor_cached_matches_cached_single": all(r["content_sha256"] == cached_ref for r in a4),
        "neighbor_cached_matches_cold": all(r["content_sha256"] == cold_ref for r in a4),
        "neighbor_generations_nonempty": all(
            n is not None and "error" not in n and n.get("content_chars", 0) > 0
            for n in (a2_neighbors + a4_neighbors)
        ),
        "prime_matches_cold": all(p["content_sha256"] == cold_ref for p in a4_primes),
        "distinct_digests_total": sorted(
            {r["content_sha256"] for r in a1 + a2 + a3 + a4}
        ),
    }
    return {
        "audit": "determinism_audit_e1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "device_label": device_label,
        "build_info": build_info,
        "total_slots": props.get("total_slots"),
        "repeats": repeats,
        "n_predict": n_predict,
        "neighbor_n_predict": neighbor_n_predict,
        "seed": seed,
        "neighbor_lead_s": neighbor_lead_s,
        "probe_token_length": len(probe_tokens),
        "neighbor_token_length": len(neighbor_tokens),
        "checks": checks,
        "observations": observations,
        "arms": {
            "A1_cold_single": a1,
            "A2_cold_neighbor": a2,
            "A3_cached_single_prime_then_repeat": {"prime": prime, "repeats": a3},
            "A4_cached_neighbor": {
                "primes": a4_primes,
                "repeats": a4,
            },
        },
        "neighbors": {"A2": a2_neighbors, "A4": a4_neighbors},
        "note": "observations are non-gating: identical or divergent outputs are both valid findings; "
        "no direction was pre-registered (review book 7.1)",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True, help="isolated llama-server base URL (never production 8901)")
    parser.add_argument("--repeats", type=int, default=4)
    parser.add_argument("--n-predict", type=int, default=48)
    parser.add_argument("--neighbor-n-predict", type=int, default=96)
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--neighbor-lead-s", type=float, default=0.25)
    parser.add_argument("--device-label", default="unlabeled")
    parser.add_argument("--out", default=None, help="also write the JSON result to this path")
    args = parser.parse_args()
    if args.repeats < 1:
        raise SystemExit("--repeats must be >= 1")
    if ":8901" in args.base_url:
        raise SystemExit("refusing to run against production port 8901; use an isolated port")
    result = run(
        args.base_url,
        args.repeats,
        args.n_predict,
        args.neighbor_n_predict,
        args.seed,
        args.neighbor_lead_s,
        device_label=args.device_label,
    )
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")
    print(text)
    raise SystemExit(0 if result["status"] == "PASS" else 2)


if __name__ == "__main__":
    main()
