#!/usr/bin/env python3
"""Portable llama.cpp hybrid attention+SSM exact-prefix mechanical canary.

Motivated by a real hybrid-SSM serving incident where prefix-cache slot
indexing treated the KV block size as the recurrent-state block size; prefix
hits read out-of-bounds all-zero SSM states and the server kept answering
silently wrong. Hybrid backends therefore get their own canary: the stock
mechanical reuse-bound checks, plus generation-content identity checks that a
zero/stale SSM state would break:

- reference content: cold greedy generation for prompt A.
- exact_A_replay_content_identical: exact-prefix replay reproduces the cold
  content bit-identically.
- A_after_B_content_identical: A after a diverging B reproduces the reference
  content (no silently accepted stale or zeroed SSM state).
- R-chain extension: multi-round extends only reuse the true common prefix.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
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


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def determinism_pre_gate(base_url: str, repeats: int, device_label: str) -> dict[str, Any]:
    """Step 0 gate: greedy determinism audit must PASS before the canary runs."""
    script = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "determinism_audit.py"
    )
    if not os.path.isfile(script):
        raise SystemExit(
            "determinism_audit.py not found next to the qualification kits; "
            "the pre-gate is mandatory and cannot be skipped"
        )
    completed = subprocess.run(
        [
            sys.executable,
            script,
            "--base-url",
            base_url,
            "--repeats",
            str(repeats),
            "--device-label",
            device_label,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    audit = json.loads(completed.stdout)
    audit["exit_code"] = completed.returncode
    return audit


def run(base_url: str, n_predict: int) -> dict[str, Any]:
    common = (
        "StateBraid hybrid-SSM qualification fixture. This text is intentionally stable and mechanical. "
        "The backend must reuse only the true token prefix and must never expose stale KV or SSM state. "
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
    reference = completion(base_url, tokens["A"], n_predict=n_predict)
    results: dict[str, Any] = {
        "cold_A": timing(reference),
        "cold_A_generation": {
            **timing(reference),
            "content_sha256": digest(str(reference.get("content", ""))),
            "content_nonempty": bool(reference.get("content")),
            "stop_type": reference.get("stop_type"),
        },
    }
    replay = completion(base_url, tokens["A"], n_predict=n_predict)
    results["exact_A_replay"] = {
        **timing(replay),
        "content_sha256": digest(str(replay.get("content", ""))),
    }
    extension = completion(base_url, tokens["Aext"])
    results["A_extension"] = timing(extension)
    diverge = completion(base_url, tokens["B"])
    results["B_diverge"] = timing(diverge)
    after_b = completion(base_url, tokens["A"], n_predict=n_predict)
    results["A_after_B"] = {
        **timing(after_b),
        "content_sha256": digest(str(after_b.get("content", ""))),
    }
    erase(base_url)
    results["R1_cold"] = timing(completion(base_url, tokens["R1"]))
    results["R2_extend"] = timing(completion(base_url, tokens["R2"]))
    results["R3_extend"] = timing(completion(base_url, tokens["R3"]))
    erase(base_url)
    results["A_after_erase"] = timing(completion(base_url, tokens["A"]))

    reference_content = str(reference.get("content", ""))
    checks = {
        "cold_A_zero": results["cold_A"]["cache_n"] == 0,
        "cold_A_content_nonempty": results["cold_A_generation"]["content_nonempty"],
        "exact_A_safe_replay": (
            results["exact_A_replay"]["cache_n"] <= len(tokens["A"]) - 1
            and results["exact_A_replay"]["prompt_n"] >= 1
        ),
        "exact_A_replay_content_identical": (
            results["exact_A_replay"]["content_sha256"]
            == results["cold_A_generation"]["content_sha256"]
        ),
        "extension_not_over_lcp": results["A_extension"]["cache_n"] <= lcp(tokens["A"], tokens["Aext"]),
        "B_not_over_true_lcp": results["B_diverge"]["cache_n"] <= lcp(tokens["Aext"], tokens["B"]),
        "A_after_B_not_stale": results["A_after_B"]["cache_n"] <= lcp(tokens["A"], tokens["B"]),
        "A_after_B_content_identical": (
            results["A_after_B"]["content_sha256"] == results["cold_A_generation"]["content_sha256"]
        ),
        "R1_cold_zero": results["R1_cold"]["cache_n"] == 0,
        "R2_not_over_lcp": results["R2_extend"]["cache_n"] <= lcp(tokens["R1"], tokens["R2"]),
        "R3_not_over_lcp": results["R3_extend"]["cache_n"] <= lcp(tokens["R2"], tokens["R3"]),
        "erase_resets": results["A_after_erase"]["cache_n"] == 0,
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "n_predict": n_predict,
        "token_lengths": {name: len(value) for name, value in tokens.items()},
        "lcp_Aext_B": lcp(tokens["Aext"], tokens["B"]),
        "lcp_A_B": lcp(tokens["A"], tokens["B"]),
        "results": results,
        "checks": checks,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8902")
    parser.add_argument("--n-predict", type=int, default=12)
    parser.add_argument("--audit-repeats", type=int, default=4)
    parser.add_argument("--device-label", default="unlabeled")
    args = parser.parse_args()
    audit = determinism_pre_gate(args.base_url, args.audit_repeats, args.device_label)
    if audit["status"] != "PASS" or audit["exit_code"] != 0:
        print(
            json.dumps(
                {
                    "status": "FAIL",
                    "aborted_before_canary": True,
                    "determinism_audit": audit,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        raise SystemExit(2)
    result = run(args.base_url, args.n_predict)
    result["determinism_audit"] = audit
    print(json.dumps(result, indent=2, ensure_ascii=False))
    raise SystemExit(0 if result["status"] == "PASS" else 2)


if __name__ == "__main__":
    main()
