"""Reusable capability-gated conformance checks for StateBraid backend adapters."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from statebraid.backend.contract import (
    BackendCapability,
    BackendDescriptor,
    LookupObservation,
)


class ConformanceStatus(str, Enum):
    PASS = "pass"
    SKIP = "skip"
    FAIL = "fail"


class ConformanceFailure(RuntimeError):
    """Internal assertion type converted into a FAIL result by the runner."""


@dataclass(frozen=True)
class ConformanceResult:
    name: str
    status: ConformanceStatus
    required_capabilities: tuple[BackendCapability, ...]
    detail: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "status": self.status.value,
            "required_capabilities": [
                item.value for item in self.required_capabilities
            ],
            "detail": self.detail,
        }


@dataclass(frozen=True)
class BackendConformanceReport:
    descriptor: BackendDescriptor
    results: tuple[ConformanceResult, ...]

    @property
    def passed(self) -> bool:
        return all(result.status is not ConformanceStatus.FAIL for result in self.results)

    @property
    def passed_count(self) -> int:
        return sum(result.status is ConformanceStatus.PASS for result in self.results)

    @property
    def skipped_count(self) -> int:
        return sum(result.status is ConformanceStatus.SKIP for result in self.results)

    @property
    def failed_count(self) -> int:
        return sum(result.status is ConformanceStatus.FAIL for result in self.results)

    def to_dict(self) -> dict[str, object]:
        return {
            "backend": self.descriptor.to_dict(),
            "passed": self.passed,
            "passed_count": self.passed_count,
            "skipped_count": self.skipped_count,
            "failed_count": self.failed_count,
            "results": [result.to_dict() for result in self.results],
        }


class BackendConformanceDriver(Protocol):
    """Adapter-author test driver; not a production serving API.

    A driver may expose test-only fault injection/introspection. The production
    adapter remains free to use a local in-process API, an HTTP API, or another
    transport as long as the declared mechanics can be demonstrated.
    """

    descriptor: BackendDescriptor

    def cache_key(self, trust_domain: str, tokens: Sequence[int]) -> object: ...

    def payload(self, nbytes: int) -> object: ...

    def seed(
        self,
        trust_domain: str,
        tokens: Sequence[int],
        payload: object,
        *,
        role: str,
        nbytes: int,
    ) -> None:
        """Prepare resident test state without implying admission ownership.

        This is a conformance-fixture primitive only.  It lets an adapter prove
        lookup/isolation/attribution/generation capabilities even when the real
        serving backend keeps admission and residency authority.
        """
        ...

    def admit(
        self,
        trust_domain: str,
        tokens: Sequence[int],
        payload: object,
        *,
        role: str,
        nbytes: int,
        predecessor_tokens: Sequence[int] | None = None,
    ) -> bool: ...

    def lookup(self, trust_domain: str, tokens: Sequence[int]) -> LookupObservation: ...

    def contains(self, trust_domain: str, tokens: Sequence[int]) -> bool: ...

    def entry_hits(self, trust_domain: str, tokens: Sequence[int]) -> int | None: ...

    def resident_stats(self) -> tuple[int, int]: ...

    def fail_next_insert(self) -> None: ...

    def generation_safe_exact(
        self, trust_domain: str, tokens: Sequence[int]
    ) -> LookupObservation: ...


DriverFactory = Callable[[int, int], BackendConformanceDriver]


def _caps(*items: BackendCapability) -> tuple[BackendCapability, ...]:
    return tuple(items)


def _require(condition: bool, detail: str) -> None:
    if not condition:
        raise ConformanceFailure(detail)


def _run_case(
    descriptor: BackendDescriptor,
    name: str,
    required: tuple[BackendCapability, ...],
    case: Callable[[], None],
) -> ConformanceResult:
    missing = tuple(item for item in required if not descriptor.supports(item))
    if missing:
        return ConformanceResult(
            name=name,
            status=ConformanceStatus.SKIP,
            required_capabilities=required,
            detail="unsupported: " + ", ".join(item.value for item in missing),
        )
    try:
        case()
    except Exception as exc:  # conformance must convert backend failures to evidence
        return ConformanceResult(
            name=name,
            status=ConformanceStatus.FAIL,
            required_capabilities=required,
            detail=f"{type(exc).__name__}: {exc}",
        )
    return ConformanceResult(
        name=name,
        status=ConformanceStatus.PASS,
        required_capabilities=required,
    )


def run_backend_conformance(factory: DriverFactory) -> BackendConformanceReport:
    """Run the standard mechanical suite against one backend-driver factory."""

    descriptor = factory(4, 1_000).descriptor
    results: list[ConformanceResult] = []

    def namespace_identity() -> None:
        driver = factory(4, 1_000)
        left = driver.cache_key("tenant-a", [1, 2, 3])
        same = driver.cache_key("tenant-a", [1, 2, 3])
        other = driver.cache_key("tenant-b", [1, 2, 3])
        _require(left == same, "same trust domain produced unstable cache identity")
        _require(left != other, "different trust domains produced the same cache identity")

    results.append(
        _run_case(
            descriptor,
            "namespace_identity",
            _caps(BackendCapability.NAMESPACE_ISOLATION),
            namespace_identity,
        )
    )

    def namespace_isolation() -> None:
        driver = factory(4, 1_000)
        payload = driver.payload(40)
        driver.seed("tenant-a", [1, 2, 3], payload, role="stable", nbytes=40)
        miss = driver.lookup("tenant-b", [1, 2, 3])
        _require(not miss.hit, "tenant-b reused tenant-a cache state")
        _require(miss.remaining == (1, 2, 3), "cross-domain miss remainder changed")
        hit = driver.lookup("tenant-a", [1, 2, 3])
        _require(hit.hit and hit.exact, "same-domain exact reuse was not observed")
        _require(hit.payload is payload, "same-domain lookup returned a different payload")

    results.append(
        _run_case(
            descriptor,
            "namespace_isolation_and_same_domain_reuse",
            _caps(
                BackendCapability.NAMESPACE_ISOLATION,
                BackendCapability.PREFIX_LOOKUP,
            ),
            namespace_isolation,
        )
    )

    def hit_attribution() -> None:
        driver = factory(4, 1_000)
        payload = driver.payload(40)
        driver.seed("tenant-a", [2, 3], payload, role="stable", nbytes=40)
        observation = driver.lookup("tenant-a", [2, 3, 4, 5])
        _require(observation.hit, "nearest-prefix lookup missed a resident prefix")
        _require(observation.remaining == (4, 5), "lookup remainder is not exact")
        _require(observation.matched_key is not None, "hit lacks matched key")
        if observation.matched_key is not None:
            _require(
                observation.matched_key.tokens == (2, 3),
                "hit was attributed to the wrong prefix",
            )
        _require(
            driver.entry_hits("tenant-a", [2, 3]) == 1,
            "actual prefix did not receive exactly one hit credit",
        )
        _require(
            driver.entry_hits("tenant-a", [2, 3, 4, 5]) is None,
            "full prompt received false hit attribution",
        )

    results.append(
        _run_case(
            descriptor,
            "actual_prefix_hit_attribution",
            _caps(
                BackendCapability.PREFIX_LOOKUP,
                BackendCapability.HIT_ATTRIBUTION,
            ),
            hit_attribution,
        )
    )

    def stable_active_lineage() -> None:
        driver = factory(2, 1_000)
        stable = driver.payload(40)
        active = driver.payload(50)
        successor = driver.payload(60)
        _require(
            driver.admit("tenant-a", [5, 6], stable, role="stable", nbytes=40),
            "stable admission failed",
        )
        _require(
            driver.admit("tenant-a", [5, 6, 7], active, role="active", nbytes=50),
            "active admission failed",
        )
        _require(
            driver.admit(
                "tenant-a",
                [5, 6, 7, 8],
                successor,
                role="active",
                nbytes=60,
                predecessor_tokens=[5, 6, 7],
            ),
            "active-successor admission failed",
        )
        _require(driver.contains("tenant-a", [5, 6]), "stable lane disappeared")
        _require(
            not driver.contains("tenant-a", [5, 6, 7]),
            "active predecessor was not compacted",
        )
        _require(
            driver.contains("tenant-a", [5, 6, 7, 8]),
            "active successor is not resident",
        )
        count, total_bytes = driver.resident_stats()
        _require(count == 2, f"expected 2 resident sequences; found {count}")
        _require(total_bytes == 100, f"expected 100 resident bytes; found {total_bytes}")

    results.append(
        _run_case(
            descriptor,
            "stable_active_lineage_and_residency",
            _caps(BackendCapability.ADMISSION_RESIDENCY),
            stable_active_lineage,
        )
    )

    def capacity() -> None:
        driver = factory(1, 45)
        first = driver.payload(30)
        second = driver.payload(30)
        _require(
            driver.admit("tenant-a", [10], first, role="user", nbytes=30),
            "first capacity admission failed",
        )
        _require(
            driver.admit("tenant-a", [11], second, role="user", nbytes=30),
            "second capacity admission failed",
        )
        count, total_bytes = driver.resident_stats()
        _require(count <= 1, f"sequence limit exceeded: {count}")
        _require(total_bytes <= 45, f"byte limit exceeded: {total_bytes}")
        _require(driver.contains("tenant-a", [11]), "new admitted entry is not resident")

    results.append(
        _run_case(
            descriptor,
            "sequence_and_byte_capacity",
            _caps(BackendCapability.ADMISSION_RESIDENCY),
            capacity,
        )
    )

    def rollback() -> None:
        driver = factory(2, 1_000)
        old = driver.payload(40)
        _require(
            driver.admit("tenant-a", [20, 21], old, role="active", nbytes=40),
            "rollback baseline admission failed",
        )
        driver.fail_next_insert()
        raised = False
        try:
            driver.admit(
                "tenant-a",
                [20, 21, 22],
                driver.payload(50),
                role="active",
                nbytes=50,
                predecessor_tokens=[20, 21],
            )
        except Exception:
            raised = True
        _require(raised, "fault injection did not reach transactional insert")
        _require(driver.contains("tenant-a", [20, 21]), "rollback lost old active state")
        _require(
            not driver.contains("tenant-a", [20, 21, 22]),
            "rollback retained failed successor state",
        )
        count, total_bytes = driver.resident_stats()
        _require(
            count == 1 and total_bytes == 40,
            f"rollback residency mismatch: count={count}, bytes={total_bytes}",
        )

    results.append(
        _run_case(
            descriptor,
            "transaction_rollback",
            _caps(
                BackendCapability.ADMISSION_RESIDENCY,
                BackendCapability.TRANSACTIONAL_MUTATION,
                BackendCapability.ROLLBACK,
            ),
            rollback,
        )
    )

    def generation_safety() -> None:
        driver = factory(3, 1_000)
        driver.seed(
            "tenant-a", [30, 31], driver.payload(40), role="stable", nbytes=40
        )
        driver.seed(
            "tenant-a",
            [30, 31, 32],
            driver.payload(50),
            role="active",
            nbytes=50,
        )
        exact = driver.lookup("tenant-a", [30, 31, 32])
        _require(exact.exact, "generation-safety setup did not produce an exact hit")
        safe = driver.generation_safe_exact("tenant-a", [30, 31, 32])
        _require(safe.hit, "generation-safe replay lost all reusable state")
        _require(safe.remaining == (32,), "exact hit did not replay one token")
        _require(safe.matched_key is not None, "generation-safe replay lacks prefix key")
        if safe.matched_key is not None:
            _require(
                safe.matched_key.tokens == (30, 31),
                "generation-safe replay did not resolve from N-1",
            )

    results.append(
        _run_case(
            descriptor,
            "generation_safe_exact_reuse",
            _caps(
                BackendCapability.PREFIX_LOOKUP,
                BackendCapability.GENERATION_SAFETY,
            ),
            generation_safety,
        )
    )

    return BackendConformanceReport(descriptor=descriptor, results=tuple(results))


__all__ = [
    "BackendConformanceDriver",
    "BackendConformanceReport",
    "ConformanceFailure",
    "ConformanceResult",
    "ConformanceStatus",
    "DriverFactory",
    "run_backend_conformance",
]
