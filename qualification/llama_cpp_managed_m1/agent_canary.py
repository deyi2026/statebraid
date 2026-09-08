#!/usr/bin/env python3
"""Portable autonomous-tool continuation canary for managed M1."""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from typing import Any

from statebraid.adapters.llama_cpp_managed import (
    LLAMA_CPP_MANAGED_REFERENCE_SHA,
    LlamaCppManagedHTTPAdapter,
    LlamaCppStateBraidPromptCache,
)
from statebraid.cache.policy import CacheKey


MARKER = "EXACT-MANAGED-RAM-42"
FILE_PATH = f"/fixture/{MARKER}.txt"
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a text file",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    }
]


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


def render(base_url: str, model: str, messages: list[dict[str, Any]]) -> tuple[str, list[int]]:
    response = request_json(
        base_url,
        "/apply-template",
        {"model": model, "messages": messages, "tools": TOOLS, "tool_choice": "auto"},
    )
    prompt = str(response["prompt"])
    return prompt, tokenize(base_url, prompt)


def chat(base_url: str, model: str, messages: list[dict[str, Any]], max_tokens: int) -> dict[str, Any]:
    return dict(
        request_json(
            base_url,
            "/v1/chat/completions",
            {
                "model": model,
                "messages": messages,
                "tools": TOOLS,
                "tool_choice": "auto",
                "temperature": 0,
                "seed": 1234,
                "stream": False,
                "max_tokens": max_tokens,
            },
        )
    )


def lcp(left: list[int], right: list[int]) -> int:
    matched = 0
    for lhs, rhs in zip(left, right):
        if lhs != rhs:
            break
        matched += 1
    return matched


def unrelated_tokens(base_url: str, label: str) -> list[int]:
    return tokenize(
        base_url,
        f"INTERLEAVING SESSION {label}\n" + "unrelated deterministic payload for slot replacement\n" * 64,
    )


def run_round(base_url: str, model: str, label: str, *, prime_unrelated_first: bool) -> dict[str, Any]:
    adapter = LlamaCppManagedHTTPAdapter(base_url, id_slot=0)
    cache = LlamaCppStateBraidPromptCache(adapter, max_sequences=3, max_bytes=2 * 1024**3)
    if int(adapter.managed_store()["n_handles"]) != 0:
        raise AssertionError("agent canary requires an empty initial managed store")

    if prime_unrelated_first:
        prime = unrelated_tokens(base_url, f"{label}-PRIME")
        if cache.lookup(cache.namespace, prime).matched_tokens != 0:
            raise AssertionError("reverse-order priming unexpectedly reused state")

    messages1 = [
        {"role": "system", "content": "Use the provided tool when asked to read a file. Do not guess file contents."},
        {"role": "user", "content": f"Read {FILE_PATH} with the read_file tool."},
    ]
    prompt1, prompt1_tokens = render(base_url, model, messages1)
    cold = cache.lookup(cache.namespace, prompt1_tokens)
    if cold.matched_tokens != 0:
        raise AssertionError("first Agent turn must be cold")

    first = chat(base_url, model, messages1, 128)
    message = first["choices"][0]["message"]
    calls = message.get("tool_calls") or []
    if len(calls) != 1:
        raise AssertionError("expected exactly one autonomous tool call")
    function = calls[0]["function"]
    arguments = json.loads(function["arguments"])
    if function["name"] != "read_file" or arguments.get("path") != FILE_PATH:
        raise AssertionError("tool semantics changed")

    messages2 = messages1 + [
        message,
        {"role": "tool", "tool_call_id": calls[0]["id"], "content": f"MARKER_{MARKER}=42"},
        {"role": "user", "content": "Report only the exact marker value from the tool result."},
    ]
    prompt2, prompt2_tokens = render(base_url, model, messages2)
    slots = request_json(base_url, "/slots")
    if not isinstance(slots, list) or len(slots) != 1:
        raise AssertionError("agent canary requires exactly one live slot")
    slot_n_tokens = slots[0].get("n_prompt_tokens")
    if not isinstance(slot_n_tokens, int) or isinstance(slot_n_tokens, bool):
        raise AssertionError("invalid live slot token count")
    if slot_n_tokens <= 0 or slot_n_tokens > len(prompt2_tokens):
        raise AssertionError("live slot token count is not a valid continuation prefix")

    state_tokens = prompt2_tokens[:slot_n_tokens]
    state = cache.capture_current(state_tokens)
    if not cache.admit_captured(state_tokens, state, role="active"):
        raise AssertionError("active Agent state admission rejected")
    active_key = CacheKey.from_tokens(cache.namespace, state_tokens)
    if cache.policy.capture_state().entries[active_key].hits != 0:
        raise AssertionError("capture/admission must not count as a factual hit")

    overwritten = cache.lookup(cache.namespace, unrelated_tokens(base_url, f"{label}-OVERWRITE"))
    if overwritten.matched_tokens != 0:
        raise AssertionError("unrelated session unexpectedly reused Agent state")

    expected_lcp = lcp(state_tokens, prompt2_tokens)
    resumed = cache.lookup(cache.namespace, prompt2_tokens)
    if not 0 < resumed.matched_tokens <= expected_lcp:
        raise AssertionError("managed continuation reuse is outside the exact prefix bound")
    if cache.policy.capture_state().entries[active_key].hits != 1:
        raise AssertionError("factual continuation must increment exactly one active hit")

    second = chat(base_url, model, messages2, 96)
    final = second["choices"][0]["message"].get("content", "") or ""
    final_correct = final.strip().endswith("42")
    if not final_correct:
        raise AssertionError("agent final answer changed")

    if not cache.trim_to(n_sequences=0, n_bytes=0):
        raise AssertionError("unable to trim managed policy to empty")
    cache.backend.assert_physical_matches_registry()
    adapter.clear_live_slot()
    after_cleanup = dict(adapter.managed_store())
    if after_cleanup["n_handles"] != 0 or after_cleanup["n_bytes"] != 0:
        raise AssertionError("managed store did not clean up")

    return {
        "label": label,
        "prime_unrelated_first": prime_unrelated_first,
        "a1_prompt_hash": hashlib.sha256(prompt1.encode()).hexdigest(),
        "a1_prompt_tokens": len(prompt1_tokens),
        "tool_name": function["name"],
        "tool_path": arguments["path"],
        "captured_tokens": state.n_tokens,
        "captured_bytes": state.nbytes,
        "next_prompt_hash": hashlib.sha256(prompt2.encode()).hexdigest(),
        "next_prompt_tokens": len(prompt2_tokens),
        "expected_lcp": expected_lcp,
        "formal_lookup": {"cache_n": resumed.matched_tokens, "prompt_n": len(resumed.remaining)},
        "final": final.strip(),
        "final_correct": final_correct,
        "cleanup_empty": after_cleanup["n_handles"] == 0 and after_cleanup["n_bytes"] == 0,
    }


def run(base_url: str, model: str) -> dict[str, Any]:
    props = request_json(base_url, "/props")
    build_info = str(props["build_info"])
    source_prefix = build_info.rsplit("-", 1)[-1]
    if not LLAMA_CPP_MANAGED_REFERENCE_SHA.startswith(source_prefix):
        raise AssertionError("wrong managed source")
    forward = run_round(base_url, model, "forward", prime_unrelated_first=False)
    reverse = run_round(base_url, model, "reverse", prime_unrelated_first=True)
    checks = {
        "same_tool_semantics": forward["tool_name"] == reverse["tool_name"] == "read_file",
        "same_next_prompt_hash": forward["next_prompt_hash"] == reverse["next_prompt_hash"],
        "both_formal_reuse_nonzero": forward["formal_lookup"]["cache_n"] > 0 and reverse["formal_lookup"]["cache_n"] > 0,
        "both_reuse_bounded": forward["formal_lookup"]["cache_n"] <= forward["expected_lcp"] and reverse["formal_lookup"]["cache_n"] <= reverse["expected_lcp"],
        "both_final_correct": forward["final_correct"] and reverse["final_correct"],
        "both_cleanup_empty": forward["cleanup_empty"] and reverse["cleanup_empty"],
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "build_info": build_info,
        "managed_reference_sha": LLAMA_CPP_MANAGED_REFERENCE_SHA,
        "props_total_slots": props.get("total_slots"),
        "forward": forward,
        "reverse": reverse,
        "checks": checks,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8901")
    parser.add_argument("--model", default="qwen3.6-35b-a3b-pruned-v2")
    args = parser.parse_args()
    result = run(args.base_url, args.model)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    raise SystemExit(0 if result["status"] == "PASS" else 2)


if __name__ == "__main__":
    main()
