"""Harness <-> StateBraid Integration Contract v0.1.

The contract is deliberately narrower than any agent-harness API.  It transports
only mechanical compute identity/constraints into StateBraid and factual compute
results back out.  There is no extension bag for task/evidence semantics.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, fields
from typing import Any

from statebraid.backend import BackendCapability, BackendDescriptor
from statebraid.cache.namespace import validate_trust_domain

HARNESS_INTEGRATION_CONTRACT_VERSION = "0.1"
_BACKEND_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:@+-]{0,255}\Z")

FORBIDDEN_SEMANTIC_FIELDS: tuple[str, ...] = (
    "goal",
    "task_status",
    "task_strategy",
    "evidence_importance",
    "selected_evidence",
    "working_state",
    "working_state_summary",
    "checkpoint_meaning",
    "tool_relevance",
    "completion_state",
    "next_action",
    "fold_decision",
    "retry_desirability",
    "cache_tag",
)


class IntegrationContractViolation(ValueError):
    """Raised when a harness attempts to cross the compute-only boundary."""


@dataclass(frozen=True)
class MechanicalResourceConstraints:
    """Optional hard compute-resource constraints supplied by the harness/operator."""

    max_sequences: int | None = None
    max_bytes: int | None = None
    transient_reserve: int | None = None

    def __post_init__(self) -> None:
        for label, value, allow_zero in (
            ("max_sequences", self.max_sequences, False),
            ("max_bytes", self.max_bytes, False),
            ("transient_reserve", self.transient_reserve, True),
        ):
            if value is None:
                continue
            if not isinstance(value, int) or isinstance(value, bool):
                raise TypeError(f"{label} must be an integer or None")
            minimum = 0 if allow_zero else 1
            if value < minimum:
                raise ValueError(f"{label} must be >= {minimum}")

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "MechanicalResourceConstraints":
        allowed = {field.name for field in fields(cls)}
        unknown = sorted(set(payload) - allowed)
        if unknown:
            raise IntegrationContractViolation(
                "unknown/non-mechanical resource fields: " + ", ".join(unknown)
            )
        return cls(**dict(payload))

    def to_dict(self) -> dict[str, int | None]:
        return {
            "max_sequences": self.max_sequences,
            "max_bytes": self.max_bytes,
            "transient_reserve": self.transient_reserve,
        }


@dataclass(frozen=True)
class HarnessComputeRequest:
    """The complete v0.1 input surface from a harness into StateBraid."""

    backend_identity: str
    trust_domain: str
    token_ids: tuple[int, ...]
    resource_constraints: MechanicalResourceConstraints = MechanicalResourceConstraints()

    def __post_init__(self) -> None:
        if not isinstance(self.backend_identity, str) or _BACKEND_ID_RE.fullmatch(
            self.backend_identity
        ) is None:
            raise ValueError(
                "backend_identity must be a bounded mechanical ASCII identity token"
            )
        object.__setattr__(self, "trust_domain", validate_trust_domain(self.trust_domain))
        normalized = tuple(self.token_ids)
        if not normalized:
            raise ValueError("token_ids must contain at least one exact token id")
        for token in normalized:
            if not isinstance(token, int) or isinstance(token, bool) or token < 0:
                raise ValueError("token_ids must contain non-negative integer token ids")
        object.__setattr__(self, "token_ids", normalized)
        if not isinstance(self.resource_constraints, MechanicalResourceConstraints):
            raise TypeError("resource_constraints must be MechanicalResourceConstraints")

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "HarnessComputeRequest":
        allowed = {field.name for field in fields(cls)}
        unknown = sorted(set(payload) - allowed)
        if unknown:
            forbidden = sorted(set(unknown).intersection(FORBIDDEN_SEMANTIC_FIELDS))
            if forbidden:
                raise IntegrationContractViolation(
                    "agent-semantic fields are forbidden by Harness <-> StateBraid "
                    "Integration Contract v0.1: " + ", ".join(forbidden)
                )
            raise IntegrationContractViolation(
                "unknown integration request fields: " + ", ".join(unknown)
            )
        if "resource_constraints" in payload:
            raw_constraints = payload["resource_constraints"]
            if not isinstance(raw_constraints, Mapping):
                raise IntegrationContractViolation(
                    "resource_constraints must be an object of mechanical limits"
                )
            constraints = MechanicalResourceConstraints.from_mapping(raw_constraints)
        else:
            constraints = MechanicalResourceConstraints()
        try:
            token_ids = tuple(payload["token_ids"])
            backend_identity = payload["backend_identity"]
            trust_domain = payload["trust_domain"]
        except KeyError as exc:
            raise IntegrationContractViolation(
                f"missing required integration field: {exc.args[0]}"
            ) from exc
        except TypeError as exc:
            raise IntegrationContractViolation("token_ids must be an iterable of integers") from exc
        return cls(
            backend_identity=backend_identity,
            trust_domain=trust_domain,
            token_ids=token_ids,
            resource_constraints=constraints,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "backend_identity": self.backend_identity,
            "trust_domain": self.trust_domain,
            "token_ids": list(self.token_ids),
            "resource_constraints": self.resource_constraints.to_dict(),
        }


@dataclass(frozen=True)
class HarnessComputeFacts:
    """Mechanical facts StateBraid may return to a harness.

    Unknown facts stay ``None``.  The schema intentionally has no reason/summary/
    recommendation text fields that could become a second semantic control plane.
    """

    backend_identity: str
    trust_domain: str
    request_token_ids: tuple[int, ...]
    actual_reused_prefix: tuple[int, ...] | None = None
    cache_hit_tokens: int | None = None
    admitted: bool | None = None
    evicted_entries: int | None = None
    generation_replay_tokens: int | None = None
    resident_sequences: int | None = None
    resident_bytes: int | None = None

    def __post_init__(self) -> None:
        request = HarnessComputeRequest(
            backend_identity=self.backend_identity,
            trust_domain=self.trust_domain,
            token_ids=self.request_token_ids,
        )
        object.__setattr__(self, "backend_identity", request.backend_identity)
        object.__setattr__(self, "trust_domain", request.trust_domain)
        object.__setattr__(self, "request_token_ids", request.token_ids)
        prefix = self.actual_reused_prefix
        if prefix is not None:
            normalized_prefix = tuple(prefix)
            if request.token_ids[: len(normalized_prefix)] != normalized_prefix:
                raise ValueError("actual_reused_prefix must be an exact request prefix")
            object.__setattr__(self, "actual_reused_prefix", normalized_prefix)
            if self.cache_hit_tokens is not None and self.cache_hit_tokens != len(
                normalized_prefix
            ):
                raise ValueError(
                    "cache_hit_tokens must equal actual_reused_prefix length when both are known"
                )
        for label, value in (
            ("cache_hit_tokens", self.cache_hit_tokens),
            ("evicted_entries", self.evicted_entries),
            ("generation_replay_tokens", self.generation_replay_tokens),
            ("resident_sequences", self.resident_sequences),
            ("resident_bytes", self.resident_bytes),
        ):
            if value is not None and (
                not isinstance(value, int) or isinstance(value, bool) or value < 0
            ):
                raise ValueError(f"{label} must be a non-negative integer or None")
        if self.admitted is not None and not isinstance(self.admitted, bool):
            raise TypeError("admitted must be bool or None")
        if self.cache_hit_tokens is not None and self.cache_hit_tokens > len(request.token_ids):
            raise ValueError("cache_hit_tokens cannot exceed request token count")
        if (
            self.generation_replay_tokens is not None
            and self.generation_replay_tokens > len(request.token_ids)
        ):
            raise ValueError("generation_replay_tokens cannot exceed request token count")

    def to_dict(self) -> dict[str, Any]:
        return {
            "backend_identity": self.backend_identity,
            "trust_domain": self.trust_domain,
            "request_token_ids": list(self.request_token_ids),
            "actual_reused_prefix": (
                None
                if self.actual_reused_prefix is None
                else list(self.actual_reused_prefix)
            ),
            "cache_hit_tokens": self.cache_hit_tokens,
            "admitted": self.admitted,
            "evicted_entries": self.evicted_entries,
            "generation_replay_tokens": self.generation_replay_tokens,
            "resident_sequences": self.resident_sequences,
            "resident_bytes": self.resident_bytes,
        }


@dataclass(frozen=True)
class BackendCompatibilityVerdict:
    """Mechanical capability result for a backend already chosen by the caller."""

    backend_identity: str
    descriptor_name: str
    required_capabilities: tuple[BackendCapability, ...]
    missing_capabilities: tuple[BackendCapability, ...]

    @property
    def compatible(self) -> bool:
        return not self.missing_capabilities

    def to_dict(self) -> dict[str, Any]:
        return {
            "backend_identity": self.backend_identity,
            "descriptor_name": self.descriptor_name,
            "compatible": self.compatible,
            "required_capabilities": [item.value for item in self.required_capabilities],
            "missing_capabilities": [item.value for item in self.missing_capabilities],
        }


def check_backend_compatibility(
    *,
    backend_identity: str,
    descriptor: BackendDescriptor,
    required_capabilities: Iterable[BackendCapability],
) -> BackendCompatibilityVerdict:
    """Check a caller-selected backend; never select or rank a backend."""

    if not isinstance(backend_identity, str) or _BACKEND_ID_RE.fullmatch(backend_identity) is None:
        raise ValueError("backend_identity must be a bounded mechanical ASCII identity token")
    required = tuple(sorted({BackendCapability(item) for item in required_capabilities}, key=lambda item: item.value))
    missing = tuple(item for item in required if not descriptor.supports(item))
    return BackendCompatibilityVerdict(
        backend_identity=backend_identity,
        descriptor_name=descriptor.name,
        required_capabilities=required,
        missing_capabilities=missing,
    )


def integration_contract_metadata() -> dict[str, Any]:
    return {
        "integration_contract_version": HARNESS_INTEGRATION_CONTRACT_VERSION,
        "direction": "harness-to-statebraid-compute-only",
        "allowed_inputs": [
            "backend_identity",
            "trusted ownership/trust_domain",
            "exact token/request identity",
            "mechanical resource constraints",
        ],
        "allowed_outputs": [
            "actual reused prefix",
            "cache-hit token facts",
            "admission/eviction facts",
            "generation-safe reuse facts",
            "resource/capacity facts",
        ],
        "forbidden_semantic_fields": list(FORBIDDEN_SEMANTIC_FIELDS),
        "backend_selection": "external-harness-or-gateway-owned",
        "statebraid_role": "mechanical compatibility gate and compute-continuity facts",
    }


__all__ = [
    "FORBIDDEN_SEMANTIC_FIELDS",
    "HARNESS_INTEGRATION_CONTRACT_VERSION",
    "BackendCompatibilityVerdict",
    "HarnessComputeFacts",
    "HarnessComputeRequest",
    "IntegrationContractViolation",
    "MechanicalResourceConstraints",
    "check_backend_compatibility",
    "integration_contract_metadata",
]
