from __future__ import annotations

import argparse
import importlib
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

TASKS = [
    {
        "name": "cache_tag_contract",
        "prompt": (
            "只读审查 src/llm_loop/cognitive/cache_tags.py。必须通过只读工具核对文件，不修改任何文件。"
            "回答 system 消息默认映射到什么 cache_tag、尾部最后一条 user 映射到什么 cache_tag、"
            "tagging_enabled_for 在没有匹配端点配置时默认是开还是关。"
            "最终答案最后三行必须严格写成：\n"
            "system_tag=rules\n"
            "tail_user_tag=goal\n"
            "default_switch=OFF"
        ),
        "checks": ["system_tag=rules", "tail_user_tag=goal", "default_switch=off"],
        "evidence_terms": ["rules", "goal", "cognitive_tag_endpoints"],
    },
    {
        "name": "working_state_wiring",
        "prompt": (
            "只读审查 src/llm_loop/core/prompt_build/stages/ingress_resolution.py 与 "
            "src/llm_loop/core/episode_history.py。必须通过只读工具核对定义和 production 调用，不修改代码。"
            "判断 working_state checkpoint 的 resolve consumer 是否已经接入 production，以及 "
            "build_working_state_checkpoint producer 是否已有 production 调用点。"
            "最终答案最后两行必须严格写成：\nconsumer=WIRED\nproducer=UNWIRED"
        ),
        "checks": ["consumer=wired", "producer=unwired"],
        "evidence_terms": ["resolve_working_state_checkpoint", "build_working_state_checkpoint"],
    },
    {
        "name": "provider_truncation_fact",
        "prompt": (
            "只读审查 src/llm_loop/core/recent_continuity.py。必须通过只读工具核对，不修改代码。"
            "判断 provider truncation 的 runtime fact 是给模型事实状态，还是程序指示模型如何继续。"
            "最终答案最后一行必须严格写成：\nruntime_fact=NON_DIRECTIVE"
        ),
        "checks": ["runtime_fact=non_directive"],
        "evidence_terms": ["provider_truncated", "directive"],
    },
]


def _message_field(message: Any, name: str, default: Any = None) -> Any:
    if isinstance(message, dict):
        return message.get(name, default)
    return getattr(message, name, default)


def _canonical_call(call: Any) -> str:
    if not isinstance(call, dict):
        return repr(call)
    name = str(call.get("name") or (call.get("function") or {}).get("name") or "")
    args: Any = call.get("arguments")
    if args is None:
        args = (call.get("function") or {}).get("arguments")
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            pass
    return json.dumps([name, args], ensure_ascii=False, sort_keys=True)


def _task_row(engine: Any, task: dict[str, Any], model_ref: str) -> dict[str, Any]:
    ingress_module = importlib.import_module("llm_loop.core.trace_leak.ingress_token")
    issue_ingress = ingress_module.issue_ingress

    sid = engine.session.create(model_override=model_ref)
    started = time.perf_counter()
    result = engine.run(sid, task["prompt"], ingress=issue_ingress("cli"))
    elapsed = time.perf_counter() - started
    session = engine.session.load(sid)
    tool_evidence = "\n".join(
        str(_message_field(message, "content", ""))
        for message in session.messages
        if _message_field(message, "role", "") == "tool"
    )
    final = result.final_answer or ""
    final_cf = final.casefold()
    evidence_cf = tool_evidence.casefold()
    checks = {term: term.casefold() in final_cf for term in task["checks"]}
    evidence_checks = {term: term.casefold() in evidence_cf for term in task["evidence_terms"]}
    signatures = [_canonical_call(call) for call in result.tool_calls]
    duplicate_calls = len(signatures) - len(set(signatures))
    tokens_in = int(result.tokens_in or 0)
    cached = int(getattr(result, "tokens_cache_hit", 0) or 0)
    return {
        "task": task["name"],
        "session_id": sid,
        "elapsed_seconds": round(elapsed, 3),
        "model_used": result.model_used,
        "rounds": result.rounds,
        "tool_calls": len(result.tool_calls),
        "duplicate_tool_calls": duplicate_calls,
        "truncated": bool(result.truncated),
        "tokens_in": tokens_in,
        "tokens_out": int(result.tokens_out or 0),
        "tokens_cache_hit": cached,
        "new_prefill_tokens": max(0, tokens_in - cached),
        "cache_hit_ratio": (cached / tokens_in) if tokens_in else None,
        "completion_checks": checks,
        "completion_pass": all(checks.values()),
        "evidence_checks": evidence_checks,
        "evidence_pass": all(evidence_checks.values()),
        "final_answer": final,
        "tool_signatures": signatures,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arm", required=True, choices=["cognitive", "statebraid"])
    parser.add_argument("--lfl-root", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--model-ref", default="cognilocal/ornith-1.5-35b-a3b-mlx")
    parser.add_argument(
        "--task",
        action="append",
        choices=[task["name"] for task in TASKS],
        help="Run only the named task; repeat to select multiple tasks.",
    )
    parser.add_argument(
        "--lfl-revision",
        default="",
        help="Optional immutable LFL revision label recorded in the result.",
    )
    args = parser.parse_args()

    lfl_root = Path(args.lfl_root).resolve()
    output = Path(args.output).resolve()
    data_dir = Path(tempfile.mkdtemp(prefix=f"statebraid-phase162-{args.arm}-"))
    shutil.copy2(lfl_root / "data" / "providers.json", data_dir / "providers.json")

    os.environ.update(
        {
            "DATA_DIR": str(data_dir),
            "LLM_API_KEY": "none",
            "LLM_BASE_URL": "http://localhost:8901/v1",
            "LLM_MODEL": "ornith-1.5-35b-a3b-mlx",
            "LLM_MAX_TOKENS": "4096",
            "LLM_MAX_ITERATIONS": "8",
            "LLM_TIMEOUT_S": "600",
            "LLM_THINKING_MODE": "1",
            "COGNITIVE_TAG_ENDPOINTS": "http://localhost:8901*",
            "EMBEDDING_PROVIDER": "hash",
        }
    )
    sys.path.insert(0, str(lfl_root / "src"))
    os.chdir(lfl_root)

    config_module = importlib.import_module("llm_loop.config")
    factory_module = importlib.import_module("llm_loop.factory")
    load_settings = config_module.load_settings
    build_engine = factory_module.build_engine

    engine = build_engine(load_settings())
    try:
        selected = TASKS
        if args.task:
            selected_names = set(args.task)
            selected = [task for task in TASKS if task["name"] in selected_names]
        rows = [_task_row(engine, task, args.model_ref) for task in selected]
    finally:
        engine.close()

    totals: dict[str, int | float | None] = {
        "tasks": len(rows),
        "completion_passed": sum(row["completion_pass"] for row in rows),
        "evidence_passed": sum(row["evidence_pass"] for row in rows),
        "tool_calls": sum(row["tool_calls"] for row in rows),
        "duplicate_tool_calls": sum(row["duplicate_tool_calls"] for row in rows),
        "truncated_tasks": sum(row["truncated"] for row in rows),
        "tokens_in": sum(row["tokens_in"] for row in rows),
        "tokens_out": sum(row["tokens_out"] for row in rows),
        "tokens_cache_hit": sum(row["tokens_cache_hit"] for row in rows),
        "new_prefill_tokens": sum(row["new_prefill_tokens"] for row in rows),
        "elapsed_seconds": round(sum(row["elapsed_seconds"] for row in rows), 3),
    }
    total_tokens_in = int(totals["tokens_in"] or 0)
    total_cache_hit = int(totals["tokens_cache_hit"] or 0)
    totals["cache_hit_ratio"] = (
        total_cache_hit / total_tokens_in if total_tokens_in else None
    )
    payload = {
        "schema": "statebraid.phase16_2.lfl_ab.v1",
        "arm": args.arm,
        "lfl_revision": args.lfl_revision,
        "model_ref": args.model_ref,
        "config": {
            "max_tokens": 4096,
            "max_iterations": 8,
            "thinking_mode": "on",
            "cognitive_tag_endpoints": "http://localhost:8901*",
            "data_dir_isolated": True,
        },
        "tasks": rows,
        "totals": totals,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"arm": args.arm, "totals": totals}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
