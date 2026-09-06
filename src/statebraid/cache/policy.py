"""Backend-neutral cache working-set policy for StateBraid.

This module intentionally does not know how a backend stores KV tensors.  It
tracks only mechanical facts: cache identity, token-prefix identity, byte size,
role, reuse hits, and capacity.  Backends execute the returned plans and commit
them only after storage mutation succeeds.
"""
from __future__ import annotations

from collections import OrderedDict
import threading
from dataclasses import dataclass, field as dataclass_field, replace
from typing import Any, Hashable, Iterable, Protocol, Sequence

PIN_ROLES = frozenset({"goal", "evidence", "identity", "rules"})
ROLE_RANKS = {
    "assistant": 10,
    "user": 30,
    "system": 50,
    "active": 60,
    "stable": 70,
    "evidence": 100,
    "goal": 110,
    "identity": 120,
    "rules": 120,
}
UNKNOWN_ROLE_RANK = 20
PIN_RANK_MIN = 100


@dataclass(frozen=True)
class CacheKey:
    """Mechanical cache identity.

    ``namespace`` is backend-defined (for example a model/cache trust-domain
    key). ``tokens`` are exact prompt token ids for lineage/prefix checks.
    """

    namespace: Hashable
    tokens: tuple[int, ...]

    @classmethod
    def from_tokens(cls, namespace: Hashable, tokens: Iterable[int]) -> "CacheKey":
        return cls(namespace=namespace, tokens=tuple(tokens))


def matched_prefix_key(
    namespace: Hashable,
    prompt: Sequence[int],
    remaining: Sequence[int],
) -> CacheKey | None:
    """Return the exact prefix identity that served a cache hit.

    Backends commonly report the uncached remainder rather than the matched key.
    Reuse credit must be assigned to the prefix that actually served the request,
    not to the full prompt.
    """
    matched_len = max(0, len(prompt) - len(remaining))
    if matched_len == 0:
        return None
    return CacheKey.from_tokens(namespace, prompt[:matched_len])


@dataclass
class EntryState:
    key: CacheKey
    role: str
    nbytes: int
    pinned: bool
    hits: int = 0


@dataclass(frozen=True)
class Eviction:
    key: CacheKey
    reason: str


@dataclass(frozen=True)
class AdmissionPlan:
    accepted: bool
    key: CacheKey
    role: str
    nbytes: int
    evictions: tuple[Eviction, ...] = ()
    reason: str = "admit"


@dataclass(frozen=True)
class TrimPlan:
    evictions: tuple[Eviction, ...] = ()


@dataclass(frozen=True)
class PolicySnapshot:
    entries: dict[CacheKey, EntryState]
    buckets: dict[str, tuple[CacheKey, ...]]
    nbytes: int
    pin_evictions: int
    pin_quota_evictions: int
    active_successor_evictions: int
    stable_candidate_key: CacheKey | None
    stable_candidate_count: int
    stable_candidate_base_hits: int
    stable_candidate_promotions: int
    stable_candidate_rejections: int


class WorkingSetPolicy:
    """Plan cache admission/eviction without touching backend payloads."""

    def __init__(
        self,
        max_sequences: int = 8,
        max_bytes: int = 1 << 63,
        *,
        pin_roles: frozenset[str] = PIN_ROLES,
        transient_reserve: int | None = None,
    ) -> None:
        self.max_sequences = max(0, int(max_sequences))
        self.max_bytes = max(0, int(max_bytes))
        self.pin_roles = frozenset(pin_roles)
        default_reserve = 2 if self.max_sequences >= 4 else (1 if self.max_sequences >= 2 else 0)
        reserve = default_reserve if transient_reserve is None else int(transient_reserve)
        self.transient_reserve = max(0, min(reserve, self.max_sequences))
        self.pin_limit = max(0, self.max_sequences - self.transient_reserve)

        self._entries: dict[CacheKey, EntryState] = {}
        self._buckets: dict[str, OrderedDict[CacheKey, None]] = {}
        self._nbytes = 0

        self.pin_evictions = 0
        self.pin_quota_evictions = 0
        self.active_successor_evictions = 0
        self.stable_candidate_promotions = 0
        self.stable_candidate_rejections = 0
        self._stable_candidate_key: CacheKey | None = None
        self._stable_candidate_count = 0
        self._stable_candidate_base_hits = 0

    @property
    def nbytes(self) -> int:
        return self._nbytes

    @property
    def n_sequences(self) -> int:
        return len(self._entries)

    def entry(self, key: CacheKey) -> EntryState | None:
        return self._entries.get(key)

    def keys_for_role(self, role: str) -> tuple[CacheKey, ...]:
        return tuple(self._buckets.get(role, OrderedDict()).keys())

    def observe_hit(self, key: CacheKey) -> bool:
        entry = self._entries.get(key)
        if entry is None:
            return False
        entry.hits += 1
        return True

    def capture_state(self) -> PolicySnapshot:
        return PolicySnapshot(
            entries={
                key: EntryState(
                    key=entry.key,
                    role=entry.role,
                    nbytes=entry.nbytes,
                    pinned=entry.pinned,
                    hits=entry.hits,
                )
                for key, entry in self._entries.items()
            },
            buckets={role: tuple(bucket.keys()) for role, bucket in self._buckets.items()},
            nbytes=self._nbytes,
            pin_evictions=self.pin_evictions,
            pin_quota_evictions=self.pin_quota_evictions,
            active_successor_evictions=self.active_successor_evictions,
            stable_candidate_key=self._stable_candidate_key,
            stable_candidate_count=self._stable_candidate_count,
            stable_candidate_base_hits=self._stable_candidate_base_hits,
            stable_candidate_promotions=self.stable_candidate_promotions,
            stable_candidate_rejections=self.stable_candidate_rejections,
        )

    def restore_state(self, snapshot: PolicySnapshot) -> None:
        self._entries = {
            key: EntryState(
                key=entry.key,
                role=entry.role,
                nbytes=entry.nbytes,
                pinned=entry.pinned,
                hits=entry.hits,
            )
            for key, entry in snapshot.entries.items()
        }
        self._buckets = {
            role: OrderedDict((key, None) for key in keys)
            for role, keys in snapshot.buckets.items()
        }
        self._nbytes = snapshot.nbytes
        self.pin_evictions = snapshot.pin_evictions
        self.pin_quota_evictions = snapshot.pin_quota_evictions
        self.active_successor_evictions = snapshot.active_successor_evictions
        self._stable_candidate_key = snapshot.stable_candidate_key
        self._stable_candidate_count = snapshot.stable_candidate_count
        self._stable_candidate_base_hits = snapshot.stable_candidate_base_hits
        self.stable_candidate_promotions = snapshot.stable_candidate_promotions
        self.stable_candidate_rejections = snapshot.stable_candidate_rejections

    def snapshot(self) -> dict[str, object]:
        return {
            "nbytes": self._nbytes,
            "n_sequences": len(self._entries),
            "transient_reserve": self.transient_reserve,
            "pin_limit": self.pin_limit,
            "pin_evictions": self.pin_evictions,
            "pin_quota_evictions": self.pin_quota_evictions,
            "active_successor_evictions": self.active_successor_evictions,
            "stable_candidate_promotions": self.stable_candidate_promotions,
            "stable_candidate_rejections": self.stable_candidate_rejections,
            "stable_candidate_count": self._stable_candidate_count,
            "roles": {role: tuple(bucket.keys()) for role, bucket in self._buckets.items()},
            "entries": {
                key: EntryState(
                    key=entry.key,
                    role=entry.role,
                    nbytes=entry.nbytes,
                    pinned=entry.pinned,
                    hits=entry.hits,
                )
                for key, entry in self._entries.items()
            },
        }

    def plan_admission(
        self,
        key: CacheKey,
        *,
        role: str,
        nbytes: int,
        predecessor: CacheKey | None = None,
    ) -> AdmissionPlan:
        nbytes = max(0, int(nbytes))
        if self.max_sequences <= 0 or self.max_bytes <= 0:
            return AdmissionPlan(False, key, role, nbytes, reason="zero_capacity")
        if nbytes > self.max_bytes:
            return AdmissionPlan(False, key, role, nbytes, reason="oversized")

        evictions: list[Eviction] = []
        evicted: set[CacheKey] = set()
        existing = self._entries.get(key)

        def add_evict(candidate: CacheKey | None, reason: str) -> None:
            if candidate is not None and candidate != key and candidate not in evicted:
                evictions.append(Eviction(candidate, reason))
                evicted.add(candidate)

        if role == "stable":
            for stable_key in self.keys_for_role("stable"):
                add_evict(stable_key, "stable_rotate")

        if role == "active" and predecessor is not None:
            predecessor_entry = self._entries.get(predecessor)
            if (
                predecessor_entry is not None
                and predecessor_entry.role == "active"
                and predecessor.namespace == key.namespace
                and len(predecessor.tokens) < len(key.tokens)
                and key.tokens[: len(predecessor.tokens)] == predecessor.tokens
            ):
                add_evict(predecessor, "active_successor")

        pinned = role in self.pin_roles
        pin_count = sum(entry.pinned for entry in self._entries.values())
        unpinned_count = len(self._entries) - pin_count
        is_new = existing is None
        if pinned and not (existing and existing.pinned) and pin_count >= self.pin_limit:
            add_evict(self._oldest_pin(excluding=evicted), "pin_quota")
        elif (
            not pinned
            and is_new
            and len(self._entries) >= self.max_sequences
            and unpinned_count < self.transient_reserve
            and pin_count > 0
        ):
            add_evict(self._oldest_pin(excluding=evicted), "pin_quota")

        protected = self._working_keys() - evicted
        if role in {"stable", "active"}:
            protected.add(key)
        if not self._working_set_fits(protected, key=key, nbytes=nbytes, evicted=evicted):
            protected.clear()

        while self._projected_over_limit(key=key, nbytes=nbytes, evicted=evicted):
            victim = self._next_victim(excluding=evicted | protected | {key})
            if victim is None:
                victim = self._next_victim(excluding=evicted | {key})
            if victim is None:
                return AdmissionPlan(False, key, role, nbytes, tuple(evictions), "cannot_fit")
            add_evict(victim, "capacity")

        return AdmissionPlan(True, key, role, nbytes, tuple(evictions), "admit")

    def plan_stable_candidate(self, key: CacheKey, *, nbytes: int) -> AdmissionPlan:
        if self.max_sequences <= 0 or self.max_bytes <= 0 or nbytes > self.max_bytes:
            return AdmissionPlan(False, key, "stable", nbytes, reason="oversized_or_disabled")

        stable_keys = self.keys_for_role("stable")
        if not stable_keys:
            return replace(
                self.plan_admission(key, role="stable", nbytes=nbytes),
                reason="stable_empty",
            )

        current_key = stable_keys[0]
        current = self._entries[current_key]
        if current_key == key:
            return replace(
                self.plan_admission(key, role="stable", nbytes=nbytes),
                reason="stable_refresh",
            )

        if current.hits == 0 and len(key.tokens) > len(current_key.tokens):
            return replace(
                self.plan_admission(key, role="stable", nbytes=nbytes),
                reason="stable_cold_larger",
            )

        if self._stable_candidate_key == key:
            if current.hits > self._stable_candidate_base_hits:
                self._stable_candidate_count = 1
                self._stable_candidate_base_hits = current.hits
            else:
                self._stable_candidate_count += 1
        else:
            self._stable_candidate_key = key
            self._stable_candidate_count = 1
            self._stable_candidate_base_hits = current.hits

        if self._stable_candidate_count >= 2:
            return replace(
                self.plan_admission(key, role="stable", nbytes=nbytes),
                reason="stable_repeated_miss",
            )

        self.stable_candidate_rejections += 1
        return AdmissionPlan(False, key, "stable", nbytes, reason="stable_probation")

    def plan_trim(
        self, *, n_sequences: int | None = None, n_bytes: int | None = None
    ) -> TrimPlan:
        target_sequences = (
            self.max_sequences if n_sequences is None else max(0, int(n_sequences))
        )
        target_bytes = self.max_bytes if n_bytes is None else max(0, int(n_bytes))
        evictions: list[Eviction] = []
        evicted: set[CacheKey] = set()
        protected = self._working_keys()
        working_bytes = sum(self._entries[key].nbytes for key in protected)
        if len(protected) > target_sequences or working_bytes > target_bytes:
            protected.clear()

        def over() -> bool:
            kept = [
                entry
                for entry_key, entry in self._entries.items()
                if entry_key not in evicted
            ]
            return len(kept) > target_sequences or sum(e.nbytes for e in kept) > target_bytes

        while over():
            victim = self._next_victim(excluding=evicted | protected)
            if victim is None:
                victim = self._next_victim(excluding=evicted)
            if victim is None:
                break
            evictions.append(Eviction(victim, "trim"))
            evicted.add(victim)
        return TrimPlan(tuple(evictions))

    def commit(self, plan: AdmissionPlan) -> None:
        if not plan.accepted:
            return
        for eviction in plan.evictions:
            removed = self._remove_entry(eviction.key)
            if removed is None:
                continue
            if eviction.reason == "pin_quota":
                self.pin_quota_evictions += 1
            elif eviction.reason == "active_successor":
                self.active_successor_evictions += 1
            elif eviction.reason == "capacity" and removed.pinned:
                self.pin_evictions += 1

        self._remove_entry(plan.key)
        pinned = plan.role in self.pin_roles
        entry = EntryState(plan.key, plan.role, plan.nbytes, pinned=pinned)
        self._entries[plan.key] = entry
        self._bucket(plan.role)[plan.key] = None
        self._nbytes += plan.nbytes
        if plan.role == "stable" and plan.reason.startswith("stable_"):
            if plan.reason in {"stable_cold_larger", "stable_repeated_miss"}:
                self.stable_candidate_promotions += 1
            self._reset_stable_candidate()

    def commit_trim(self, plan: TrimPlan) -> None:
        for eviction in plan.evictions:
            removed = self._remove_entry(eviction.key)
            if removed is not None and removed.pinned:
                self.pin_evictions += 1

    def _rank(self, role: str) -> int:
        if role in self.pin_roles:
            return ROLE_RANKS.get(role, PIN_RANK_MIN)
        return ROLE_RANKS.get(role, UNKNOWN_ROLE_RANK)

    def _bucket(self, role: str) -> OrderedDict[CacheKey, None]:
        return self._buckets.setdefault(role, OrderedDict())

    def _remove_entry(self, key: CacheKey) -> EntryState | None:
        entry = self._entries.pop(key, None)
        if entry is None:
            return None
        bucket = self._buckets.get(entry.role)
        if bucket is not None:
            bucket.pop(key, None)
        self._nbytes -= entry.nbytes
        return entry

    def _ordered_keys(self) -> list[CacheKey]:
        result: list[CacheKey] = []
        for role in sorted(self._buckets, key=self._rank):
            result.extend(self._buckets[role].keys())
        return result

    def _next_victim(self, excluding: set[CacheKey]) -> CacheKey | None:
        for key in self._ordered_keys():
            if key not in excluding:
                return key
        return None

    def _oldest_pin(self, excluding: set[CacheKey]) -> CacheKey | None:
        pin_roles = sorted(
            (role for role in self._buckets if self._rank(role) >= PIN_RANK_MIN),
            key=self._rank,
        )
        for role in pin_roles:
            for key in self._buckets[role]:
                if key not in excluding:
                    return key
        return None

    def _working_keys(self) -> set[CacheKey]:
        return {
            key
            for role in ("stable", "active")
            for key in self._buckets.get(role, OrderedDict())
        }

    def _projected_state(
        self, *, key: CacheKey, nbytes: int, evicted: set[CacheKey]
    ) -> tuple[int, int]:
        kept = [entry for entry_key, entry in self._entries.items() if entry_key not in evicted and entry_key != key]
        return len(kept) + 1, sum(entry.nbytes for entry in kept) + nbytes

    def _projected_over_limit(self, *, key: CacheKey, nbytes: int, evicted: set[CacheKey]) -> bool:
        sequences, total_bytes = self._projected_state(key=key, nbytes=nbytes, evicted=evicted)
        return sequences > self.max_sequences or total_bytes > self.max_bytes

    def _working_set_fits(
        self,
        protected: set[CacheKey],
        *,
        key: CacheKey,
        nbytes: int,
        evicted: set[CacheKey],
    ) -> bool:
        count = 0
        total = 0
        for protected_key in protected:
            if protected_key == key:
                count += 1
                total += nbytes
                continue
            if protected_key in evicted:
                continue
            entry = self._entries.get(protected_key)
            if entry is not None:
                count += 1
                total += entry.nbytes
        return count <= self.max_sequences and total <= self.max_bytes

    def _reset_stable_candidate(self) -> None:
        self._stable_candidate_key = None
        self._stable_candidate_count = 0
        self._stable_candidate_base_hits = 0


class TransactionalBackend(Protocol):
    """Minimal mutation contract required by ``CacheCoordinator``.

    ``capture`` / ``restore`` snapshots are deliberately opaque references.
    StateBraid never deep-copies backend KV payloads.
    """

    def capture(self, key: CacheKey) -> Any: ...

    def restore(self, key: CacheKey, snapshot: Any) -> None: ...

    def remove(self, key: CacheKey) -> None: ...

    def insert(self, key: CacheKey, payload: object, *, role: str) -> None: ...


@dataclass
class CacheCoordinator:
    """Serialize planning + backend mutation + policy commit.

    Use the high-level ``admit_entry``, ``admit_stable_candidate``, ``trim_to``,
    and ``observe_hit`` methods in concurrent runtimes.  ``admit(plan, ...)`` and
    ``trim(plan)`` remain available for deterministic integrations that already
    serialize plan creation and application.
    """

    policy: WorkingSetPolicy
    backend: TransactionalBackend
    _lock: threading.RLock = dataclass_field(
        default_factory=threading.RLock, init=False, repr=False
    )

    def admit_entry(
        self,
        key: CacheKey,
        payload: object,
        *,
        role: str,
        nbytes: int,
        predecessor: CacheKey | None = None,
    ) -> bool:
        with self._lock:
            plan = self.policy.plan_admission(
                key, role=role, nbytes=nbytes, predecessor=predecessor
            )
            return self.admit(plan, payload)

    def admit_stable_candidate(
        self, key: CacheKey, payload: object, *, nbytes: int
    ) -> bool:
        with self._lock:
            plan = self.policy.plan_stable_candidate(key, nbytes=nbytes)
            return self.admit(plan, payload)

    def observe_hit(self, key: CacheKey) -> bool:
        with self._lock:
            return self.policy.observe_hit(key)

    def trim_to(
        self, *, n_sequences: int | None = None, n_bytes: int | None = None
    ) -> bool:
        with self._lock:
            plan = self.policy.plan_trim(n_sequences=n_sequences, n_bytes=n_bytes)
            return self.trim(plan)

    def admit(self, plan: AdmissionPlan, payload: object) -> bool:
        with self._lock:
            if not plan.accepted:
                return False
            policy_before = self.policy.capture_state()
            affected = [eviction.key for eviction in plan.evictions]
            if plan.key not in affected:
                affected.append(plan.key)
            captured = {key: self.backend.capture(key) for key in affected}
            try:
                for eviction in plan.evictions:
                    self.backend.remove(eviction.key)
                self.backend.remove(plan.key)
                self.backend.insert(plan.key, payload, role=plan.role)
                self.policy.commit(plan)
                return True
            except Exception:
                self._restore_backend_and_policy(policy_before, affected, captured)
                raise

    def trim(self, plan: TrimPlan) -> bool:
        with self._lock:
            if not plan.evictions:
                return False
            policy_before = self.policy.capture_state()
            affected = [eviction.key for eviction in plan.evictions]
            captured = {key: self.backend.capture(key) for key in affected}
            try:
                for eviction in plan.evictions:
                    self.backend.remove(eviction.key)
                self.policy.commit_trim(plan)
                return True
            except Exception:
                self._restore_backend_and_policy(policy_before, affected, captured)
                raise

    def _restore_backend_and_policy(self, policy_before, affected, captured) -> None:
        self.policy.restore_state(policy_before)
        for key in affected:
            try:
                self.backend.remove(key)
            except Exception:
                pass
        for key, snapshot in captured.items():
            if snapshot is not None:
                self.backend.restore(key, snapshot)
