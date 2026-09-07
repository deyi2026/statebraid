"""Compatibility probe for a running llama-server public HTTP surface."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Mapping

from statebraid.adapters.llama_cpp import (
    LLAMA_CPP_BACKEND_DESCRIPTOR,
    LLAMA_CPP_REFERENCE_SHA,
    JSONTransport,
    UrllibJSONTransport,
)
from statebraid.backend import BACKEND_CONTRACT_VERSION, capability_values

_BUILD_COMMIT_RE = re.compile(r"(?:^|[- ])([0-9a-f]{7,40})(?:$|[ )])")


@dataclass(frozen=True)
class LlamaCppCompatibilityReport:
    reachable: bool
    compatible: bool
    slots_endpoint: bool
    slot_count: int
    total_slots: int | None
    build_info: str | None
    source_commit: str | None
    reference_source_match: bool
    issues: tuple[str, ...]
    reference_sha: str = LLAMA_CPP_REFERENCE_SHA
    backend_contract_version: str = BACKEND_CONTRACT_VERSION
    declared_capabilities: tuple[str, ...] = capability_values(
        LLAMA_CPP_BACKEND_DESCRIPTOR.capabilities
    )
    integration_level: str = LLAMA_CPP_BACKEND_DESCRIPTOR.integration_level
    namespace_isolation: bool = False
    single_domain_only: bool = True
    runtime_qualified: bool = False

    @property
    def reference_qualified(self) -> bool:
        return self.compatible and self.reference_source_match

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["reference_qualified"] = self.reference_qualified
        return payload


def _extract_commit(build_info: str | None) -> str | None:
    if not build_info:
        return None
    matches = _BUILD_COMMIT_RE.findall(build_info.lower())
    if not matches:
        return None
    # build_info may contain a decimal build number; the commit is conventionally
    # the final hex field. Prefer the final match.
    return matches[-1]


def probe_llama_cpp_server(
    base_url: str = "http://127.0.0.1:8080",
    *,
    timeout: float = 5.0,
    transport: JSONTransport | None = None,
) -> LlamaCppCompatibilityReport:
    client = transport or UrllibJSONTransport(base_url, timeout=timeout)
    try:
        props = client.get_json("/props")
        slots = client.get_json("/slots")
    except Exception as exc:
        return LlamaCppCompatibilityReport(
            reachable=False,
            compatible=False,
            slots_endpoint=False,
            slot_count=0,
            total_slots=None,
            build_info=None,
            source_commit=None,
            reference_source_match=False,
            issues=(f"llama.cpp public API probe failed: {type(exc).__name__}: {exc}",),
        )

    if not isinstance(props, Mapping):
        return LlamaCppCompatibilityReport(
            reachable=True,
            compatible=False,
            slots_endpoint=isinstance(slots, list),
            slot_count=0,
            total_slots=None,
            build_info=None,
            source_commit=None,
            reference_source_match=False,
            issues=("llama.cpp /props response is not an object",),
        )
    if not isinstance(slots, list):
        return LlamaCppCompatibilityReport(
            reachable=True,
            compatible=False,
            slots_endpoint=False,
            slot_count=0,
            total_slots=(
                props.get("total_slots")
                if isinstance(props.get("total_slots"), int)
                and not isinstance(props.get("total_slots"), bool)
                else None
            ),
            build_info=(props.get("build_info") if isinstance(props.get("build_info"), str) else None),
            source_commit=None,
            reference_source_match=False,
            issues=("llama.cpp /slots response is not a list",),
        )

    valid_slots = [
        item
        for item in slots
        if isinstance(item, Mapping)
        and isinstance(item.get("id"), int)
        and not isinstance(item.get("id"), bool)
    ]
    build_info = props.get("build_info")
    if not isinstance(build_info, str):
        build_info = None
    total_slots_raw = props.get("total_slots")
    total_slots = (
        total_slots_raw
        if isinstance(total_slots_raw, int)
        and not isinstance(total_slots_raw, bool)
        and total_slots_raw > 0
        else None
    )
    source_commit = _extract_commit(build_info)
    reference_match = bool(
        source_commit
        and (
            LLAMA_CPP_REFERENCE_SHA.startswith(source_commit)
            or source_commit.startswith(LLAMA_CPP_REFERENCE_SHA)
        )
    )

    issues: list[str] = []
    compatible = True
    if len(valid_slots) != len(slots) or not valid_slots:
        compatible = False
        issues.append("llama.cpp /slots lacks at least one valid integer slot id")
    if build_info is None:
        compatible = False
        issues.append("llama.cpp /props lacks build_info")
    elif source_commit is None:
        compatible = False
        issues.append("llama.cpp build_info does not expose a parseable commit hash")
    elif not reference_match:
        compatible = False
        issues.append(
            "running llama.cpp commit differs from the Phase 8 audited reference; "
            "capability qualification is fail-closed for unaudited source"
        )
    if total_slots is None:
        compatible = False
        issues.append("llama.cpp /props lacks a positive integer total_slots")
    elif total_slots != len(valid_slots):
        compatible = False
        issues.append(
            "llama.cpp /props total_slots does not match the valid /slots entries"
        )
    issues.append(
        "single-domain reuse observation only; shared prompt cache has no StateBraid trust namespace"
    )

    return LlamaCppCompatibilityReport(
        reachable=True,
        compatible=compatible,
        slots_endpoint=True,
        slot_count=len(valid_slots),
        total_slots=total_slots,
        build_info=build_info,
        source_commit=source_commit,
        reference_source_match=reference_match,
        issues=tuple(issues),
    )


__all__ = [
    "LlamaCppCompatibilityReport",
    "probe_llama_cpp_server",
]
