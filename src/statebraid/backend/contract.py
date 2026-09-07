"""Backend Contract v0.2 for StateBraid compute-continuity adapters.

The contract is intentionally capability-based. A backend may expose only a
safe subset; declaring one capability never implies unrelated runtime support.
StateBraid owns compute-continuity identity/policy. The serving backend keeps
ownership of model execution, attention/batching, KV storage, and KV transport.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any, Hashable, Protocol, runtime_checkable

from statebraid.cache.policy import CacheKey

BACKEND_CONTRACT_VERSION = "0.2"

STATEBRAID_OWNS: tuple[str, ...] = (
    "exact namespace + token cache identity",
    "stable/active lineage policy",
    "admission and residency policy when delegated by the backend",
    "transactional mutation orchestration and rollback semantics",
    "actual-prefix hit attribution",
    "generation-safe exact-reuse semantics",
    "factual compute-continuity telemetry",
)

BACKEND_OWNS: tuple[str, ...] = (
    "model execution",
    "attention kernels",
    "continuous batching and scheduler execution",
    "KV tensor representation and physical storage",
    "KV transport, tiering, persistence, and distributed transfer",
)


class BackendCapability(str, Enum):
    """Mechanical capabilities an adapter can expose to StateBraid."""

    NAMESPACE_ISOLATION = "namespace_isolation"
    PREFIX_LOOKUP = "prefix_lookup"
    ADMISSION_RESIDENCY = "admission_residency"
    TRANSACTIONAL_MUTATION = "transactional_mutation"
    ROLLBACK = "rollback"
    HIT_ATTRIBUTION = "hit_attribution"
    GENERATION_SAFETY = "generation_safety"


_CAPABILITY_DEPENDENCIES: dict[BackendCapability, frozenset[BackendCapability]] = {
    BackendCapability.ADMISSION_RESIDENCY: frozenset(
        {BackendCapability.TRANSACTIONAL_MUTATION}
    ),
    BackendCapability.ROLLBACK: frozenset(
        {BackendCapability.TRANSACTIONAL_MUTATION}
    ),
    BackendCapability.HIT_ATTRIBUTION: frozenset({BackendCapability.PREFIX_LOOKUP}),
    BackendCapability.GENERATION_SAFETY: frozenset({BackendCapability.PREFIX_LOOKUP}),
}


class UnsupportedBackendCapability(RuntimeError):
    """Raised when a caller requires a capability the backend did not declare."""


@dataclass(frozen=True)
class BackendDescriptor:
    """Machine-readable declaration for one StateBraid backend adapter.

    This descriptor states adapter mechanics only. It does not widen the
    separately versioned runtime support/qualification scope.
    """

    name: str
    adapter: str
    capabilities: frozenset[BackendCapability]
    contract_version: str = BACKEND_CONTRACT_VERSION
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        normalized = frozenset(BackendCapability(item) for item in self.capabilities)
        object.__setattr__(self, "capabilities", normalized)
        if self.contract_version != BACKEND_CONTRACT_VERSION:
            raise ValueError(
                "backend descriptor contract version must be "
                f"{BACKEND_CONTRACT_VERSION}; found {self.contract_version!r}"
            )
        for capability in normalized:
            dependencies = _CAPABILITY_DEPENDENCIES.get(capability, frozenset())
            missing = dependencies - normalized
            if missing:
                missing_text = ", ".join(sorted(item.value for item in missing))
                raise ValueError(
                    f"{capability.value} requires undeclared capabilities: {missing_text}"
                )

    def supports(self, *capabilities: BackendCapability) -> bool:
        return all(BackendCapability(item) in self.capabilities for item in capabilities)

    def require(self, *capabilities: BackendCapability) -> None:
        missing = [
            BackendCapability(item)
            for item in capabilities
            if BackendCapability(item) not in self.capabilities
        ]
        if missing:
            text = ", ".join(sorted(item.value for item in missing))
            raise UnsupportedBackendCapability(
                f"backend {self.name!r} does not declare: {text}"
            )

    @property
    def integration_level(self) -> str:
        observe = {
            BackendCapability.NAMESPACE_ISOLATION,
            BackendCapability.PREFIX_LOOKUP,
            BackendCapability.HIT_ATTRIBUTION,
        }
        managed = observe | {
            BackendCapability.ADMISSION_RESIDENCY,
            BackendCapability.TRANSACTIONAL_MUTATION,
            BackendCapability.ROLLBACK,
        }
        generation_safe = managed | {BackendCapability.GENERATION_SAFETY}
        if generation_safe.issubset(self.capabilities):
            return "generation-safe-managed"
        if managed.issubset(self.capabilities):
            return "managed"
        if observe.issubset(self.capabilities):
            return "observe"
        if BackendCapability.NAMESPACE_ISOLATION in self.capabilities:
            return "identity-only"
        return "partial"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "adapter": self.adapter,
            "contract_version": self.contract_version,
            "integration_level": self.integration_level,
            "capabilities": sorted(item.value for item in self.capabilities),
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class LookupObservation:
    """Normalized actual-prefix reuse observation.

    A backend may provide this before execution or as execution-coupled factual
    telemetry.  The observation always represents the prefix that was actually
    reusable/served, not a speculative semantic estimate.
    """

    namespace: Hashable
    prompt: tuple[int, ...]
    remaining: tuple[int, ...]
    payload: Any | None
    matched_key: CacheKey | None

    @classmethod
    def from_backend_result(
        cls,
        namespace: Hashable,
        prompt: Sequence[int],
        payload: Any | None,
        remaining: Sequence[int],
    ) -> "LookupObservation":
        prompt_tokens = tuple(prompt)
        remaining_tokens = tuple(remaining)
        if len(remaining_tokens) > len(prompt_tokens):
            raise ValueError("backend lookup remainder is longer than the prompt")
        matched_len = len(prompt_tokens) - len(remaining_tokens)
        if remaining_tokens != prompt_tokens[matched_len:]:
            raise ValueError("backend lookup remainder is not an exact prompt suffix")
        if payload is None and matched_len != 0:
            raise ValueError("backend reported a matched prefix without a payload")
        if payload is not None and matched_len == 0:
            raise ValueError("backend returned a payload without a matched prefix")
        matched_key = (
            CacheKey.from_tokens(namespace, prompt_tokens[:matched_len])
            if matched_len
            else None
        )
        return cls(
            namespace=namespace,
            prompt=prompt_tokens,
            remaining=remaining_tokens,
            payload=payload,
            matched_key=matched_key,
        )

    @property
    def hit(self) -> bool:
        return self.matched_key is not None

    @property
    def exact(self) -> bool:
        return self.hit and not self.remaining

    @property
    def matched_tokens(self) -> int:
        return 0 if self.matched_key is None else len(self.matched_key.tokens)


@runtime_checkable
class PrefixLookupBackend(Protocol):
    descriptor: BackendDescriptor

    def lookup(
        self, namespace: Hashable, tokens: Sequence[int]
    ) -> LookupObservation: ...


@runtime_checkable
class TransactionalMutationBackend(Protocol):
    descriptor: BackendDescriptor

    def capture(self, key: CacheKey) -> Any: ...

    def restore(self, key: CacheKey, snapshot: Any) -> None: ...

    def remove(self, key: CacheKey) -> None: ...

    def insert(self, key: CacheKey, payload: object, *, role: str) -> None: ...


def capability_values(
    capabilities: Iterable[BackendCapability],
) -> tuple[str, ...]:
    """Return deterministic string values for telemetry/serialization."""

    return tuple(sorted(BackendCapability(item).value for item in capabilities))


__all__ = [
    "BACKEND_CONTRACT_VERSION",
    "BACKEND_OWNS",
    "STATEBRAID_OWNS",
    "BackendCapability",
    "BackendDescriptor",
    "LookupObservation",
    "PrefixLookupBackend",
    "TransactionalMutationBackend",
    "UnsupportedBackendCapability",
    "capability_values",
]
