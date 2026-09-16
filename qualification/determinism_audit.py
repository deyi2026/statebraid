#!/usr/bin/env python3
"""Portable llama.cpp greedy determinism audit (qualification pre-gate).

Motivated by a real hybrid-SSM serving incident: the same greedy request,
repeated with identical parameters, returned different completions on some
backends (non-deterministic top-k kernel). Before any prefix-reuse matrix is
meaningful, the backend must first be shown deterministic under greedy
sampling, both on the cold-prefill path and on the exact cache-replay path.

Checks:
- cold_repeat_identical: N cold completions (no prompt cache) bit-identical.
- cached_repeat_identical: N completions with exact-prefix cache replay
  bit-identical among themselves.
- replay_matches_cold: the cached-path completion equals the cold-path
  completion, i.e. reusing the cached prefix must not change the answer.
- generation_nonempty: the greedy completion is not empty.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from typing import Any


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


def completion(
    base_url: str,
    tokens: list[int],
    *,
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
                "id_slot": 0,
                "cache_prompt": cache_prompt,
                "n_cache_reuse": 0,
                "n_predict": n_predict,
                "stream": False,
                "temperature": 0,
                "seed": seed,
            },
        )
    )


def erase(base_url: str) -> None:
    request_json(base_url, "/slots/0?action=erase", {})


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def run(base_url: str, repeats: int, n_predict: int, seed: int) -> dict[str, Any]:
    prompt = (
        "StateBraid determinism audit fixture. This text is intentionally stable and mechanical. "
        "The backend must return bit-identical completions for identical greedy requests. "
    ) * 24
    prompt += "\nRepeat one short deterministic sentence about the weather on a calm morning."
    tokens = tokenize(base_url, prompt)

    erase(base_url)
    cold = [
        completion(base_url, tokens, cache_prompt=False, n_predict=n_predict, seed=seed)
        for _ in range(repeats)
    ]
    erase(base_url)
    cached = [
        completion(base_url, tokens, cache_prompt=True, n_predict=n_predict, seed=seed)
        for _ in range(repeats)
    ]

    cold_contents = [str(response.get("content", "")) for response in cold]
    cached_contents = [str(response.get("content", "")) for response in cached]
    checks = {
        "cold_repeat_identical": len(set(cold_contents)) == 1,
        "cached_repeat_identical": len(set(cached_contents)) == 1,
        "replay_matches_cold": cold_contents[0] == cached_contents[0],
        "generation_nonempty": bool(cold_contents[0]),
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "repeats": repeats,
        "n_predict": n_predict,
        "seed": seed,
        "token_length": len(tokens),
        "cold_content_sha256": digest(cold_contents[0]),
        "cached_content_sha256": digest(cached_contents[0]),
        "cold_distinct_contents": len(set(cold_contents)),
        "cached_distinct_contents": len(set(cached_contents)),
        "stop_types": sorted({str(response.get("stop_type")) for response in cold + cached}),
        "checks": checks,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8901")
    parser.add_argument("--repeats", type=int, default=4)
    parser.add_argument("--n-predict", type=int, default=24)
    parser.add_argument("--seed", type=int, default=1234)
    args = parser.parse_args()
    result = run(args.base_url, args.repeats, args.n_predict, args.seed)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    raise SystemExit(0 if result["status"] == "PASS" else 2)


if __name__ == "__main__":
    main()
