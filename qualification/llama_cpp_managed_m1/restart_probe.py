#!/usr/bin/env python3
"""Two-step managed M1 restart-epoch probe without preserving opaque handles in Git."""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from statebraid.adapters.llama_cpp_managed import (
    LlamaCppManagedHTTPAdapter,
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


def prepare(base_url: str, state_file: Path) -> dict[str, object]:
    adapter = LlamaCppManagedHTTPAdapter(base_url, id_slot=0)
    store = dict(adapter.managed_store())
    if store["n_handles"] != 0:
        raise AssertionError("restart prepare requires an empty managed store")
    tokens = list(
        request_json(
            base_url,
            "/tokenize",
            {"content": "STATEBRAID MANAGED RESTART PROBE " * 64, "add_special": False},
        )["tokens"]
    )
    request_json(
        base_url,
        "/completion",
        {
            "prompt": tokens,
            "id_slot": 0,
            "cache_prompt": True,
            "n_cache_reuse": 0,
            "n_predict": 0,
            "stream": False,
            "temperature": 0,
            "seed": 1234,
        },
    )
    state, _evicted = adapter.capture_current_state(tokens)  # adapter API returns (state, evicted)
    payload = {
        "epoch": adapter.managed_epoch,
        "handle": state.handle,
        "n_tokens": state.n_tokens,
        "n_bytes": state.nbytes,
    }
    state_file.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    return {
        "status": "PREPARED",
        "captured_tokens": state.n_tokens,
        "captured_bytes": state.nbytes,
        "instruction": "Restart the same exact managed llama-server, then run verify with the same transient state file.",
    }


def verify(base_url: str, state_file: Path) -> dict[str, object]:
    before = json.loads(state_file.read_text(encoding="utf-8"))
    adapter = LlamaCppManagedHTTPAdapter(base_url, id_slot=0)
    store = dict(adapter.managed_store())
    stale_restore_http_400 = False
    stale_restore_error_code = None
    try:
        request_json(
            base_url,
            "/statebraid/cache",
            {
                "action": "restore",
                "epoch": before["epoch"],
                "id_slot": 0,
                "handle": before["handle"],
            },
        )
    except urllib.error.HTTPError as exc:
        stale_restore_http_400 = exc.code == 400
        try:
            body = json.loads(exc.read().decode())
            stale_restore_error_code = body.get("error", {}).get("code")
        except Exception:
            stale_restore_error_code = None
    checks = {
        "epoch_changed": adapter.managed_epoch != before["epoch"],
        "store_empty_after_restart": store["n_handles"] == 0 and store["n_bytes"] == 0,
        "stale_restore_rejected_400": stale_restore_http_400,
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "stale_restore_error_code": stale_restore_error_code,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare", "verify"))
    parser.add_argument("--base-url", default="http://127.0.0.1:8901")
    parser.add_argument("--state-file", type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.base_url, args.state_file) if args.mode == "prepare" else verify(args.base_url, args.state_file)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result["status"] == "FAIL":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
