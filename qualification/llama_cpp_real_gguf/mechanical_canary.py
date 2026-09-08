#!/usr/bin/env python3
"""Portable stock-llama.cpp exact-prefix mechanical qualification canary."""

from __future__ import annotations

import argparse
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


def completion(base_url: str, tokens: list[int], n_predict: int = 0) -> dict[str, Any]:
    return dict(
        request_json(
            base_url,
            "/completion",
            {
                "prompt": tokens,
                "id_slot": 0,
                "cache_prompt": True,
                "n_cache_reuse": 0,
                "n_predict": n_predict,
                "stream": False,
                "temperature": 0,
                "seed": 1234,
            },
        )
    )


def timing(response: dict[str, Any]) -> dict[str, int]:
    timings = response["timings"]
    return {
        "cache_n": int(timings["cache_n"]),
        "prompt_n": int(timings["prompt_n"]),
    }


def lcp(left: list[int], right: list[int]) -> int:
    matched = 0
    for lhs, rhs in zip(left, right):
        if lhs != rhs:
            break
        matched += 1
    return matched


def erase(base_url: str) -> None:
    request_json(base_url, "/slots/0?action=erase", {})


def run(base_url: str) -> dict[str, Any]:
    common = (
        "StateBraid L1 real GGUF qualification fixture. This text is intentionally stable and mechanical. "
        "The backend must reuse only the true token prefix and must never expose stale KV state. "
    ) * 24
    texts = {
        "A": common + "\nBRANCH=A. Return a short deterministic continuation about alpha.",
        "Aext": common
        + "\nBRANCH=A. Return a short deterministic continuation about alpha."
        + "\nCONTINUATION=A2. The prefix above must remain reusable while these suffix tokens are new.",
        "B": common + "\nBRANCH=B. Return a short deterministic continuation about beta.",
        "R1": common + "\nMULTI ROUND ONE. Fact one: amber. Fact two: cedar.",
    }
    texts["R2"] = texts["R1"] + "\nMULTI ROUND TWO. Fact three: delta. Fact four: ember."
    texts["R3"] = texts["R2"] + "\nMULTI ROUND THREE. Fact five: frost. Fact six: granite."
    tokens = {name: tokenize(base_url, text) for name, text in texts.items()}

    erase(base_url)
    results: dict[str, Any] = {
        "cold_A": timing(completion(base_url, tokens["A"])),
        "exact_A": timing(completion(base_url, tokens["A"])),
    }
    generated = completion(base_url, tokens["A"], n_predict=12)
    results["exact_A_generation"] = {
        **timing(generated),
        "content_nonempty": bool(generated.get("content")),
        "stop_type": generated.get("stop_type"),
    }
    results["A_extension"] = timing(completion(base_url, tokens["Aext"]))
    results["B_diverge"] = timing(completion(base_url, tokens["B"]))
    results["A_after_B"] = timing(completion(base_url, tokens["A"]))
    erase(base_url)
    results["R1_cold"] = timing(completion(base_url, tokens["R1"]))
    results["R2_extend"] = timing(completion(base_url, tokens["R2"]))
    results["R3_extend"] = timing(completion(base_url, tokens["R3"]))
    erase(base_url)
    results["A_after_erase"] = timing(completion(base_url, tokens["A"]))

    checks = {
        "cold_A_zero": results["cold_A"]["cache_n"] == 0,
        "exact_A_safe_replay": (
            results["exact_A"]["cache_n"] <= len(tokens["A"]) - 1
            and results["exact_A"]["prompt_n"] >= 1
        ),
        "exact_generation_safe": (
            results["exact_A_generation"]["cache_n"] <= len(tokens["A"]) - 1
            and results["exact_A_generation"]["prompt_n"] >= 1
            and results["exact_A_generation"]["content_nonempty"]
        ),
        "extension_not_over_lcp": results["A_extension"]["cache_n"] <= lcp(tokens["A"], tokens["Aext"]),
        "B_not_over_true_lcp": results["B_diverge"]["cache_n"] <= lcp(tokens["Aext"], tokens["B"]),
        "A_after_B_not_stale": results["A_after_B"]["cache_n"] <= lcp(tokens["A"], tokens["B"]),
        "R1_cold_zero": results["R1_cold"]["cache_n"] == 0,
        "R2_not_over_lcp": results["R2_extend"]["cache_n"] <= lcp(tokens["R1"], tokens["R2"]),
        "R3_not_over_lcp": results["R3_extend"]["cache_n"] <= lcp(tokens["R2"], tokens["R3"]),
        "erase_resets": results["A_after_erase"]["cache_n"] == 0,
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "token_lengths": {name: len(value) for name, value in tokens.items()},
        "lcp_Aext_B": lcp(tokens["Aext"], tokens["B"]),
        "lcp_A_B": lcp(tokens["A"], tokens["B"]),
        "results": results,
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
