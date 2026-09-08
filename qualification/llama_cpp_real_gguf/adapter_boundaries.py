#!/usr/bin/env python3
"""Live fail-closed boundary canary for the stock llama.cpp adapter."""

from __future__ import annotations

import argparse
import json

from statebraid.adapters.llama_cpp import LlamaCppHTTPAdapter
from statebraid.backend import UnsupportedBackendCapability


def run(base_url: str) -> dict[str, object]:
    non_default_domain = False
    try:
        LlamaCppHTTPAdapter(base_url, trust_domain="tenant-a")
    except UnsupportedBackendCapability:
        non_default_domain = True

    invalid_slot = False
    adapter = LlamaCppHTTPAdapter(base_url, id_slot=3)
    try:
        adapter.lookup(adapter.namespace, [1, 2, 3])
    except ValueError as exc:
        invalid_slot = "modulo slot wrapping" in str(exc)

    checks = {
        "non_default_trust_domain_fail_closed": non_default_domain,
        "invalid_slot_fail_closed_without_modulo_wrap": invalid_slot,
    }
    return {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8901")
    args = parser.parse_args()
    result = run(args.base_url)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    raise SystemExit(0 if result["status"] == "PASS" else 2)


if __name__ == "__main__":
    main()
