"""StateBraid managed-storage M1 adapter for llama.cpp.

This module is intentionally separate from the stock llama.cpp observation
adapter.  It requires the narrow managed-storage M1 server patch and keeps
StateBraid policy ownership distinct from llama.cpp execution/storage mechanics.
"""
from __future__ import annotations

import ipaddress
from collections.abc import Hashable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from statebraid.backend import (
    BackendCapability,
    BackendDescriptor,
    BackendObservationProfile,
    BackendQualificationProfile,
    LookupObservation,
    ObservationMode,
    UnsupportedBackendCapability,
)
from statebraid.cache.policy import CacheCoordinator, CacheKey, WorkingSetPolicy

from .llama_cpp import (
    LLAMA_CPP_REFERENCE_SHA,
    LlamaCppHTTPAdapter,
    llama_cpp_source_commit,
)

LLAMA_CPP_MANAGED_REFERENCE_SHA = "0f75058ccb5c4e0d7bd029d37678435eb0d2458c"

LLAMA_CPP_MANAGED_STORAGE_DESCRIPTOR = BackendDescriptor(
    name="llama.cpp-managed-storage-m1",
    adapter="statebraid.adapters.llama_cpp_managed",
    capabilities=frozenset({BackendCapability.TRANSACTIONAL_MUTATION}),
    qualification_profile=BackendQualificationProfile(
        source_revision=(
            f"llama.cpp@{LLAMA_CPP_REFERENCE_SHA} + StateBraid managed-storage "
            f"M1@{LLAMA_CPP_MANAGED_REFERENCE_SHA}"
        ),
        observation_path="managed /statebraid/cache clear/capture/restore/drop",
        cache_mode="StateBraid exclusive policy; native --cache-ram must be 0",
        concurrency_profile="loopback-only, single slot / serial M1 prototype",
        model_class="real Qwen3.6-derived GGUF M1 evidence + tiny deterministic server tests",
        runtime_qualified=False,
        notes=(
            "Low-level storage mechanics only; policy lookup must go through the managed facade.",
            "Full physical rollback and trust-domain namespace isolation are not declared.",
        ),
    ),
)

LLAMA_CPP_MANAGED_BACKEND_DESCRIPTOR = BackendDescriptor(
    name="llama.cpp-managed-m1",
    adapter="statebraid.adapters.llama_cpp_managed",
    capabilities=frozenset(
        {
            BackendCapability.PREFIX_LOOKUP,
            BackendCapability.ADMISSION_RESIDENCY,
            BackendCapability.TRANSACTIONAL_MUTATION,
            BackendCapability.HIT_ATTRIBUTION,
            BackendCapability.GENERATION_SAFETY,
        }
    ),
    observation_profile=BackendObservationProfile(
        mode=ObservationMode.EXECUTION_COUPLED,
        may_mutate_backend_state=True,
        notes=(
            "Actual-prefix evidence still comes from bounded /completion execution.",
            "Managed residency mutations use opaque /statebraid/cache RAM handles.",
        ),
    ),
    qualification_profile=BackendQualificationProfile(
        source_revision=(
            f"llama.cpp@{LLAMA_CPP_REFERENCE_SHA} + StateBraid managed-storage "
            f"M1@{LLAMA_CPP_MANAGED_REFERENCE_SHA}"
        ),
        observation_path=(
            "managed /statebraid/cache clear/capture/restore/drop plus "
            "/completion timings.cache_n"
        ),
        cache_mode="StateBraid exclusive policy; native --cache-ram must be 0",
        concurrency_profile="loopback-only, single slot / serial M1 prototype",
        model_class="real Qwen3.6-derived GGUF M1 evidence + tiny deterministic server tests",
        runtime_qualified=False,
        notes=(
            "M1 is a real RAM managed-storage prototype, not public production qualification.",
            "No trust-domain namespace isolation is declared.",
            "Full physical rollback is not declared; remote handle retirement is reconciled post-commit.",
            "n_bytes is serialized state-payload accounting, not instantaneous OS footprint.",
            "Broader multi-slot, speculative, Linux/x86_64 and arbitrary-model support remain unqualified.",
        ),
    ),
    notes=(
        "StateBraid owns admission/residency and stable/active lineage policy only.",
        "llama.cpp owns opaque state representation, checkpoints, KV/SSM storage, scheduler and execution.",
        "Managed restore is non-destructive; explicit drop retires an opaque handle.",
        "Registry rollback is exercised, but Backend Contract rollback remains undeclared until remote physical commit/abort is qualified.",
        "A managed clear precedes each policy-directed restore to prevent hidden live-slot reuse.",
    ),
)

def llama_cpp_managed_reference_source_match(build_info: str | None) -> bool:
    """Return whether ``build_info`` identifies the exact managed M1 source."""

    source_commit = llama_cpp_source_commit(build_info)
    return bool(
        source_commit
        and (
            LLAMA_CPP_MANAGED_REFERENCE_SHA.startswith(source_commit)
            or source_commit.startswith(LLAMA_CPP_MANAGED_REFERENCE_SHA)
        )
    )

@dataclass(frozen=True)
class LlamaCppManagedStateHandle:
    """Opaque server-side RAM state selected by StateBraid policy.

    ``nbytes`` is serialized state-payload accounting reported by llama.cpp;
    it is not RSS or platform physical-footprint telemetry.
    """

    backend_identity: str
    epoch: str
    handle: str
    id_slot: int
    n_tokens: int
    nbytes: int


@dataclass(frozen=True)
class LlamaCppManagedRestore:
    key: CacheKey
    state: LlamaCppManagedStateHandle
    candidate_lcp: int


class LlamaCppManagedHTTPAdapter(LlamaCppHTTPAdapter):
    """Low-level M1 HTTP transport for opaque llama.cpp RAM state mechanics."""

    descriptor = LLAMA_CPP_MANAGED_STORAGE_DESCRIPTOR

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        # Loopback/scheme gate BEFORE the stock constructor (J-round review):
        # reject non-loopback base_url before the parent sets up transport.
        base_url = str(kwargs.get("base_url", args[0] if args else ""))
        parsed = urlparse(base_url)
        hostname = parsed.hostname or ""
        is_loopback = hostname.lower() == "localhost"
        if not is_loopback:
            try:
                is_loopback = ipaddress.ip_address(hostname).is_loopback
            except ValueError:
                is_loopback = False
        if parsed.scheme not in {"http", "https"} or not is_loopback:
            raise UnsupportedBackendCapability(
                "llama.cpp managed-storage M1 is qualified only through a loopback base_url"
            )
        super().__init__(*args, **kwargs)
        total_slots = self._require_reference_source()
        self._require_exact_slot(total_slots=total_slots)
        store = self._read_store(require_pinned_epoch=False)
        self.managed_epoch = str(store["epoch"])

    def _require_reference_source(self) -> int:
        props = self.transport.get_json("/props")
        if not isinstance(props, Mapping):
            raise UnsupportedBackendCapability(
                "llama.cpp /props did not return an object; managed source "
                "qualification cannot be established"
            )
        build_info = props.get("build_info")
        if not isinstance(build_info, str) or not llama_cpp_managed_reference_source_match(
            build_info
        ):
            source_commit = llama_cpp_source_commit(
                build_info if isinstance(build_info, str) else None
            )
            raise UnsupportedBackendCapability(
                "running llama.cpp source is not the audited managed M1 reference: "
                f"expected {LLAMA_CPP_MANAGED_REFERENCE_SHA}, "
                f"found {source_commit or 'unknown'}"
            )
        total_slots = props.get("total_slots")
        if (
            not isinstance(total_slots, int)
            or isinstance(total_slots, bool)
            or total_slots <= 0
        ):
            raise UnsupportedBackendCapability(
                "llama.cpp /props lacks a positive integer total_slots"
            )
        return total_slots

    def _read_store(self, *, require_pinned_epoch: bool = True) -> Mapping[str, Any]:
        payload = self.transport.get_json("/statebraid/cache")
        if not isinstance(payload, Mapping) or payload.get("enabled") is not True:
            raise UnsupportedBackendCapability(
                "llama.cpp managed cache endpoint is unavailable or disabled"
            )
        epoch = payload.get("epoch")
        if not isinstance(epoch, str) or not epoch:
            raise ValueError("llama.cpp managed cache returned an invalid epoch")
        if require_pinned_epoch and epoch != self.managed_epoch:
            raise UnsupportedBackendCapability(
                "llama.cpp managed-cache epoch changed; stale handles are invalid"
            )
        values: dict[str, int] = {}
        for name in ("n_handles", "n_tokens", "n_bytes"):
            value = payload.get(name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"llama.cpp managed cache returned invalid {name}")
            values[name] = value
        handles = payload.get("handles")
        if not isinstance(handles, list):
            raise ValueError("llama.cpp managed cache returned invalid handles")
        seen: set[str] = set()
        token_sum = 0
        byte_sum = 0
        for item in handles:
            if not isinstance(item, Mapping):
                raise ValueError("llama.cpp managed cache handle entry must be an object")
            handle = item.get("handle")
            n_tokens = item.get("n_tokens")
            n_bytes = item.get("n_bytes")
            if not isinstance(handle, str) or not handle or handle in seen:
                raise ValueError("llama.cpp managed cache returned invalid/duplicate handle")
            if not isinstance(n_tokens, int) or isinstance(n_tokens, bool) or n_tokens <= 0:
                raise ValueError("llama.cpp managed cache handle has invalid n_tokens")
            if not isinstance(n_bytes, int) or isinstance(n_bytes, bool) or n_bytes <= 0:
                raise ValueError("llama.cpp managed cache handle has invalid n_bytes")
            seen.add(handle)
            token_sum += n_tokens
            byte_sum += n_bytes
        if values["n_handles"] != len(handles):
            raise ValueError("llama.cpp managed cache n_handles does not match handles")
        if values["n_tokens"] != token_sum or values["n_bytes"] != byte_sum:
            raise ValueError("llama.cpp managed cache aggregate accounting is inconsistent")
        return payload

    def managed_store(self) -> Mapping[str, Any]:
        return self._read_store()

    def _post_managed(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        response = self.transport.post_json("/statebraid/cache", payload)
        if not isinstance(response, Mapping):
            raise ValueError("llama.cpp managed cache response must be an object")
        if response.get("success") is not True:
            raise ValueError("llama.cpp managed cache mutation did not report success")
        if response.get("epoch") != self.managed_epoch:
            raise UnsupportedBackendCapability(
                "llama.cpp managed-cache mutation returned a stale/different epoch"
            )
        return response

    def clear_live_slot(self) -> int:
        response = self._post_managed(
            {
                "action": "clear",
                "epoch": self.managed_epoch,
                "id_slot": self.id_slot,
            }
        )
        if response.get("id_slot") != self.id_slot:
            raise ValueError("llama.cpp managed clear returned a different slot")
        n_cleared = response.get("n_cleared")
        if not isinstance(n_cleared, int) or isinstance(n_cleared, bool) or n_cleared < 0:
            raise ValueError("llama.cpp managed clear returned invalid n_cleared")
        return n_cleared

    def capture_current_state(self) -> LlamaCppManagedStateHandle:
        response = self._post_managed(
            {
                "action": "capture",
                "epoch": self.managed_epoch,
                "id_slot": self.id_slot,
            }
        )
        if response.get("id_slot") != self.id_slot:
            raise ValueError("llama.cpp managed capture returned a different slot")
        handle = response.get("handle")
        n_tokens = response.get("n_tokens")
        nbytes = response.get("n_bytes")
        if not isinstance(handle, str) or not handle:
            raise ValueError("llama.cpp managed capture returned an invalid handle")
        if not isinstance(n_tokens, int) or isinstance(n_tokens, bool) or n_tokens <= 0:
            raise ValueError("llama.cpp managed capture returned invalid n_tokens")
        if not isinstance(nbytes, int) or isinstance(nbytes, bool) or nbytes <= 0:
            raise ValueError("llama.cpp managed capture returned invalid n_bytes")
        return LlamaCppManagedStateHandle(
            backend_identity=self.backend_identity,
            epoch=self.managed_epoch,
            handle=handle,
            id_slot=self.id_slot,
            n_tokens=n_tokens,
            nbytes=nbytes,
        )

    def _require_state_binding(self, state: LlamaCppManagedStateHandle) -> None:
        if state.backend_identity != self.backend_identity:
            raise ValueError("managed handle belongs to a different llama.cpp backend")
        if state.epoch != self.managed_epoch:
            raise UnsupportedBackendCapability("managed handle belongs to a stale epoch")
        if state.id_slot != self.id_slot:
            raise ValueError("managed handle belongs to a different llama.cpp slot")

    def lookup(
        self,
        namespace: Hashable,
        tokens: Sequence[int],
    ) -> LookupObservation:
        del namespace, tokens
        raise UnsupportedBackendCapability(
            "low-level llama.cpp managed-storage adapter does not expose policy-safe "
            "prefix lookup; use LlamaCppStateBraidPromptCache.lookup()"
        )

    def _lookup_after_policy(
        self,
        namespace: Hashable,
        tokens: Sequence[int],
    ) -> LookupObservation:
        """Run the factual bounded completion probe after facade policy preparation."""

        return super().lookup(namespace, tokens)

    def restore_state(self, state: LlamaCppManagedStateHandle) -> None:
        self._require_state_binding(state)
        response = self._post_managed(
            {
                "action": "restore",
                "epoch": self.managed_epoch,
                "id_slot": self.id_slot,
                "handle": state.handle,
            }
        )
        if response.get("handle") != state.handle or response.get("id_slot") != self.id_slot:
            raise ValueError("llama.cpp managed restore returned a different handle/slot")
        if response.get("n_tokens") != state.n_tokens or response.get("n_bytes") != state.nbytes:
            raise ValueError("llama.cpp managed restore changed state accounting")

    def drop_state(self, state: LlamaCppManagedStateHandle) -> None:
        self._require_state_binding(state)
        payload = {
            "action": "drop",
            "epoch": self.managed_epoch,
            "handle": state.handle,
        }
        try:
            response = self._post_managed(payload)
        except Exception:
            # A transport failure may occur after the server already applied
            # the drop. Reconcile against the same process epoch before deciding
            # whether cleanup is still pending. If the store itself is
            # unreachable or the epoch changed, fail closed.
            store = self.managed_store()
            handles = {
                item["handle"]
                for item in store["handles"]
                if isinstance(item, Mapping) and "handle" in item
            }
            if state.handle not in handles:
                return
            raise
        if response.get("handle") != state.handle:
            raise ValueError("llama.cpp managed drop returned a different handle")
        if response.get("n_tokens") != state.n_tokens or response.get("n_bytes") != state.nbytes:
            raise ValueError("llama.cpp managed drop changed state accounting")


class LlamaCppManagedStorageBackend:
    """Registry-rollback-safe CacheKey bindings over managed RAM handles.

    Coordinator mutation changes only local key bindings. Physical drops are
    deferred until the policy transaction has committed, so local mutation
    rollback never requires copying llama.cpp KV/SSM bytes into Python. This is
    intentionally narrower than Backend Contract physical ``ROLLBACK``.
    """

    descriptor = LLAMA_CPP_MANAGED_STORAGE_DESCRIPTOR

    def __init__(
        self,
        adapter: LlamaCppManagedHTTPAdapter,
        *,
        require_empty: bool = True,
    ) -> None:
        self.adapter = adapter
        self.records: dict[CacheKey, LlamaCppManagedStateHandle] = {}
        self._pending_drops: dict[str, LlamaCppManagedStateHandle] = {}
        if require_empty and int(adapter.managed_store()["n_handles"]) != 0:
            raise UnsupportedBackendCapability(
                "managed llama.cpp store is not empty; refusing to adopt unknown handles"
            )

    def _require_key(self, key: CacheKey) -> None:
        if key.namespace != self.adapter.namespace:
            raise UnsupportedBackendCapability(
                "managed llama.cpp storage is bound to one local-default namespace"
            )

    def _require_state(
        self, key: CacheKey, state: LlamaCppManagedStateHandle
    ) -> None:
        self._require_key(key)
        self.adapter._require_state_binding(state)
        if len(key.tokens) != state.n_tokens:
            raise ValueError(
                "managed llama.cpp state token count does not match CacheKey identity"
            )

    def capture(self, key: CacheKey) -> LlamaCppManagedStateHandle | None:
        self._require_key(key)
        return self.records.get(key)

    def restore(self, key: CacheKey, snapshot: Any) -> None:
        if not isinstance(snapshot, LlamaCppManagedStateHandle):
            raise TypeError("llama.cpp managed rollback snapshot must be an opaque handle")
        self._require_state(key, snapshot)
        self.records[key] = snapshot
        self._pending_drops.pop(snapshot.handle, None)

    def remove(self, key: CacheKey) -> None:
        self._require_key(key)
        state = self.records.pop(key, None)
        if state is not None:
            self._pending_drops[state.handle] = state

    def insert(self, key: CacheKey, payload: object, *, role: str) -> None:
        del role
        if not isinstance(payload, LlamaCppManagedStateHandle):
            raise TypeError("llama.cpp managed storage payload must be an opaque handle")
        self._require_state(key, payload)
        self.records[key] = payload
        self._pending_drops.pop(payload.handle, None)

    def capture_current(self, key: CacheKey) -> LlamaCppManagedStateHandle:
        self._require_key(key)
        # Do not allocate additional remote state while a previous physical GC
        # is unresolved. This keeps a cleanup failure from silently expanding
        # the backend beyond the logical working-set budget.
        if self._pending_drops:
            self.flush_drops()
        state = self.adapter.capture_current_state()
        try:
            self._require_state(key, state)
        except Exception:
            self.adapter.drop_state(state)
            raise
        return state

    def clear_live_slot(self) -> int:
        return self.adapter.clear_live_slot()

    def restore_live(self, key: CacheKey) -> LlamaCppManagedStateHandle:
        self._require_key(key)
        state = self.records.get(key)
        if state is None:
            raise KeyError("managed llama.cpp CacheKey is not resident")
        self.adapter.restore_state(state)
        return state

    def discard_unbound(self, state: LlamaCppManagedStateHandle) -> None:
        self.adapter._require_state_binding(state)
        self._pending_drops[state.handle] = state

    def flush_drops(self) -> int:
        referenced = {state.handle for state in self.records.values()}
        dropped = 0
        for handle, state in list(self._pending_drops.items()):
            if handle in referenced:
                self._pending_drops.pop(handle, None)
                continue
            self.adapter.drop_state(state)
            self._pending_drops.pop(handle, None)
            dropped += 1
        return dropped

    @property
    def pending_drop_bytes(self) -> int:
        return sum(state.nbytes for state in self._pending_drops.values())

    @property
    def pending_drop_count(self) -> int:
        return len(self._pending_drops)

    def assert_physical_matches_registry(self) -> None:
        store = self.adapter.managed_store()
        remote = {
            item.get("handle")
            for item in store["handles"]
            if isinstance(item, Mapping) and isinstance(item.get("handle"), str)
        }
        expected = {state.handle for state in self.records.values()}
        if remote != expected:
            raise RuntimeError(
                "managed llama.cpp physical handle set diverges from StateBraid registry"
            )


def _token_lcp(left: Sequence[int], right: Sequence[int]) -> int:
    matched = 0
    for a, b in zip(left, right):
        if int(a) != int(b):
            break
        matched += 1
    return matched


class LlamaCppStateBraidPromptCache:
    """StateBraid working-set controller for M1 llama.cpp RAM handles."""

    statebraid_policy_active = True
    descriptor = LLAMA_CPP_MANAGED_BACKEND_DESCRIPTOR

    def __init__(
        self,
        adapter: LlamaCppManagedHTTPAdapter,
        *,
        max_sequences: int,
        max_bytes: int,
        transient_reserve: int | None = None,
    ) -> None:
        self.adapter = adapter
        self.namespace = adapter.namespace
        self.policy = WorkingSetPolicy(
            max_sequences=max_sequences,
            max_bytes=max_bytes,
            transient_reserve=transient_reserve,
        )
        self.backend = LlamaCppManagedStorageBackend(adapter)
        self.coordinator = CacheCoordinator(self.policy, self.backend)

    def capture_current(
        self, state_tokens: Sequence[int]
    ) -> LlamaCppManagedStateHandle:
        key = CacheKey.from_tokens(self.namespace, state_tokens)
        return self.backend.capture_current(key)

    def admit_captured(
        self,
        state_tokens: Sequence[int],
        state: LlamaCppManagedStateHandle,
        *,
        role: str,
        predecessor_tokens: Sequence[int] | None = None,
    ) -> bool:
        key = CacheKey.from_tokens(self.namespace, state_tokens)
        predecessor = (
            None
            if predecessor_tokens is None
            else CacheKey.from_tokens(self.namespace, predecessor_tokens)
        )
        accepted = False
        try:
            accepted = self.coordinator.admit_entry(
                key,
                state,
                role=role,
                nbytes=state.nbytes,
                predecessor=predecessor,
            )
            if not accepted:
                self.backend.discard_unbound(state)
            return accepted
        except Exception:
            if all(
                resident.handle != state.handle
                for resident in self.backend.records.values()
            ):
                self.backend.discard_unbound(state)
            raise
        finally:
            self.backend.flush_drops()

    def capture_and_admit(
        self,
        state_tokens: Sequence[int],
        *,
        role: str,
        predecessor_tokens: Sequence[int] | None = None,
    ) -> bool:
        state = self.capture_current(state_tokens)
        return self.admit_captured(
            state_tokens,
            state,
            role=role,
            predecessor_tokens=predecessor_tokens,
        )

    def capture_stable_candidate(self, state_tokens: Sequence[int]) -> bool:
        key = CacheKey.from_tokens(self.namespace, state_tokens)
        state = self.backend.capture_current(key)
        accepted = False
        try:
            accepted = self.coordinator.admit_stable_candidate(
                key, state, nbytes=state.nbytes
            )
            if not accepted:
                self.backend.discard_unbound(state)
            return accepted
        except Exception:
            if all(
                resident.handle != state.handle
                for resident in self.backend.records.values()
            ):
                self.backend.discard_unbound(state)
            raise
        finally:
            self.backend.flush_drops()

    def prepare(
        self, prompt_tokens: Sequence[int]
    ) -> LlamaCppManagedRestore | None:
        prompt = tuple(int(token) for token in prompt_tokens)
        if not prompt:
            raise ValueError("managed llama.cpp prepare requires a non-empty prompt")

        # Do not allow the most recently executed live slot to become an
        # accidental second residency policy. StateBraid explicitly selects
        # zero or one resident handle for every request.
        self.backend.clear_live_slot()

        snapshot = self.policy.capture_state()
        candidates: list[tuple[int, bool, int, CacheKey]] = []
        for key, entry in snapshot.entries.items():
            if key.namespace != self.namespace:
                continue
            matched = _token_lcp(key.tokens, prompt)
            if matched <= 0:
                continue
            candidates.append(
                (matched, matched == len(key.tokens), -entry.nbytes, key)
            )
        if not candidates:
            return None

        _, _, _, key = max(candidates, key=lambda item: item[:3])
        matched = _token_lcp(key.tokens, prompt)
        state = self.backend.restore_live(key)
        return LlamaCppManagedRestore(
            key=key,
            state=state,
            candidate_lcp=matched,
        )

    def lookup(
        self,
        namespace: Hashable,
        tokens: Sequence[int],
    ) -> LookupObservation:
        if namespace != self.namespace:
            raise UnsupportedBackendCapability(
                "managed llama.cpp facade is bound to one local-default namespace"
            )
        prompt = tuple(int(token) for token in tokens)
        if not prompt:
            raise ValueError("managed llama.cpp lookup requires a non-empty prompt")

        prepared = self.prepare(prompt)
        observation = self.adapter._lookup_after_policy(self.namespace, prompt)

        if prepared is None:
            if observation.matched_tokens != 0:
                raise RuntimeError(
                    "llama.cpp reported cache reuse after StateBraid selected no "
                    "resident handle; hidden live-slot/cache reuse detected"
                )
            return observation

        if observation.matched_tokens > prepared.candidate_lcp:
            raise RuntimeError(
                "llama.cpp reported reuse beyond the StateBraid-selected exact-token "
                f"LCP: observed={observation.matched_tokens}, "
                f"selected_lcp={prepared.candidate_lcp}"
            )
        if observation.matched_tokens > 0:
            self.coordinator.observe_hit(prepared.key)
        return observation

    def generation_safe_exact(
        self,
        namespace: Hashable,
        tokens: Sequence[int],
    ) -> LookupObservation:
        observation = self.lookup(namespace, tokens)
        if not observation.remaining:
            raise ValueError(
                "llama.cpp managed exact reuse exposed an empty generation input"
            )
        return observation

    def trim_to(
        self, *, n_sequences: int | None = None, n_bytes: int | None = None
    ) -> bool:
        try:
            return self.coordinator.trim_to(
                n_sequences=n_sequences,
                n_bytes=n_bytes,
            )
        finally:
            self.backend.flush_drops()

    def activation_stats(self) -> dict[str, int | str]:
        snapshot = self.policy.capture_state()
        return {
            "mode": "statebraid-llama-managed-m1",
            "n_sequences": len(snapshot.entries),
            "n_bytes": snapshot.nbytes,
            "pending_drops": self.backend.pending_drop_count,
            "pending_drop_bytes": self.backend.pending_drop_bytes,
            "active_successor_evictions": snapshot.active_successor_evictions,
            "stable_candidate_promotions": snapshot.stable_candidate_promotions,
            "stable_candidate_rejections": snapshot.stable_candidate_rejections,
        }


__all__ = [
    "LLAMA_CPP_MANAGED_BACKEND_DESCRIPTOR",
    "LLAMA_CPP_MANAGED_REFERENCE_SHA",
    "LLAMA_CPP_MANAGED_STORAGE_DESCRIPTOR",
    "LlamaCppManagedHTTPAdapter",
    "LlamaCppManagedRestore",
    "LlamaCppManagedStateHandle",
    "LlamaCppManagedStorageBackend",
    "LlamaCppStateBraidPromptCache",
    "llama_cpp_managed_reference_source_match",
]
