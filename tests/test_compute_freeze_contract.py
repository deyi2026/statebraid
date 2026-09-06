import inspect
import unittest
from typing import Any

import statebraid.adapters as adapters
import statebraid.cache as cache
from statebraid import COMPUTE_CONTRACT_VERSION
from statebraid.cache import CacheCoordinator, CacheKey, WorkingSetPolicy


class _Backend:
    def __init__(self) -> None:
        self.values: dict[CacheKey, tuple[object, str]] = {}
        self.fail_insert = False

    def capture(self, key: CacheKey) -> Any:
        return self.values.get(key)

    def restore(self, key: CacheKey, snapshot: Any) -> None:
        if snapshot is None:
            self.values.pop(key, None)
        else:
            self.values[key] = snapshot

    def remove(self, key: CacheKey) -> None:
        self.values.pop(key, None)

    def insert(self, key: CacheKey, payload: object, *, role: str) -> None:
        self.values[key] = (payload, role)
        if self.fail_insert:
            self.fail_insert = False
            raise RuntimeError("injected failure")


class ComputeFreezeContractTest(unittest.TestCase):
    def test_contract_marker_and_required_public_subset(self) -> None:
        self.assertEqual(COMPUTE_CONTRACT_VERSION, "0.1")
        self.assertTrue(
            {
                "CacheKey",
                "matched_prefix_key",
                "WorkingSetPolicy",
                "CacheCoordinator",
                "AdmissionPlan",
                "TrimPlan",
                "ensure_generation_safe_exact_hit",
                "is_generation_safe_hybrid_checkpoint",
            }.issubset(set(cache.__all__))
        )
        self.assertTrue(
            {
                "MLXPromptCacheBackend",
                "MLXStateBraidPromptCache",
                "generation_safe_prompt_cache_hit",
            }.issubset(set(adapters.__all__))
        )

    def test_required_calling_parameters_remain_available(self) -> None:
        required = {
            WorkingSetPolicy: {"max_sequences", "max_bytes", "pin_roles", "transient_reserve"},
            CacheCoordinator.admit_entry: {"key", "payload", "role", "nbytes", "predecessor"},
            CacheCoordinator.admit_stable_candidate: {"key", "payload", "nbytes"},
            CacheCoordinator.trim_to: {"n_sequences", "n_bytes"},
            adapters.MLXStateBraidPromptCache: {
                "prompt_cache",
                "max_sequences",
                "max_bytes",
                "transient_reserve",
            },
        }
        for callable_obj, parameter_names in required.items():
            with self.subTest(callable=getattr(callable_obj, "__qualname__", repr(callable_obj))):
                self.assertTrue(parameter_names.issubset(inspect.signature(callable_obj).parameters))

    def test_default_policy_remains_semantic_blind(self) -> None:
        for role in ("goal", "rules", "evidence", "identity"):
            policy = WorkingSetPolicy(max_sequences=2, max_bytes=20)
            backend = _Backend()
            coordinator = CacheCoordinator(policy, backend)
            key = CacheKey.from_tokens("model", (1, 2, 3))
            self.assertTrue(coordinator.admit_entry(key, object(), role=role, nbytes=10))
            entry = policy.entry(key)
            self.assertIsNotNone(entry)
            assert entry is not None
            self.assertFalse(entry.pinned)
            self.assertEqual(policy.pin_roles, frozenset())

    def test_exact_identity_and_actual_prefix_credit(self) -> None:
        left = CacheKey.from_tokens("model-a", (1, 2, 3))
        same = CacheKey.from_tokens("model-a", [1, 2, 3])
        other_namespace = CacheKey.from_tokens("model-b", (1, 2, 3))
        other_tokens = CacheKey.from_tokens("model-a", (1, 2, 4))
        self.assertEqual(left, same)
        self.assertNotEqual(left, other_namespace)
        self.assertNotEqual(left, other_tokens)
        self.assertEqual(
            cache.matched_prefix_key("model-a", [1, 2, 3, 4], [3, 4]),
            CacheKey.from_tokens("model-a", (1, 2)),
        )

    def test_active_successor_compacts_only_exact_prefix_lineage(self) -> None:
        policy = WorkingSetPolicy(max_sequences=4, max_bytes=400)
        backend = _Backend()
        coordinator = CacheCoordinator(policy, backend)
        stable = CacheKey.from_tokens("model", (1, 2))
        active = CacheKey.from_tokens("model", (1, 2, 3))
        successor = CacheKey.from_tokens("model", (1, 2, 3, 4))
        self.assertTrue(coordinator.admit_entry(stable, object(), role="stable", nbytes=100))
        self.assertTrue(coordinator.admit_entry(active, object(), role="active", nbytes=100))
        self.assertTrue(
            coordinator.admit_entry(
                successor,
                object(),
                role="active",
                nbytes=100,
                predecessor=active,
            )
        )
        self.assertIsNotNone(policy.entry(stable))
        self.assertIsNone(policy.entry(active))
        self.assertIsNotNone(policy.entry(successor))

        divergent = CacheKey.from_tokens("model", (9, 9, 9))
        self.assertTrue(
            coordinator.admit_entry(
                divergent,
                object(),
                role="active",
                nbytes=100,
                predecessor=successor,
            )
        )
        self.assertIsNotNone(policy.entry(successor))

    def test_sequence_and_byte_limits_are_independent(self) -> None:
        sequence_policy = WorkingSetPolicy(max_sequences=1, max_bytes=1000)
        sequence_backend = _Backend()
        sequence_coordinator = CacheCoordinator(sequence_policy, sequence_backend)
        self.assertTrue(
            sequence_coordinator.admit_entry(
                CacheKey.from_tokens("model", (1,)), object(), role="user", nbytes=10
            )
        )
        self.assertTrue(
            sequence_coordinator.admit_entry(
                CacheKey.from_tokens("model", (2,)), object(), role="user", nbytes=10
            )
        )
        self.assertEqual(sequence_policy.n_sequences, 1)

        byte_policy = WorkingSetPolicy(max_sequences=8, max_bytes=10)
        byte_backend = _Backend()
        byte_coordinator = CacheCoordinator(byte_policy, byte_backend)
        self.assertTrue(
            byte_coordinator.admit_entry(
                CacheKey.from_tokens("model", (1,)), object(), role="user", nbytes=6
            )
        )
        self.assertTrue(
            byte_coordinator.admit_entry(
                CacheKey.from_tokens("model", (2,)), object(), role="user", nbytes=6
            )
        )
        self.assertLessEqual(byte_policy.nbytes, 10)

    def test_backend_failure_rolls_back_policy_and_backend(self) -> None:
        policy = WorkingSetPolicy(max_sequences=2, max_bytes=200)
        backend = _Backend()
        coordinator = CacheCoordinator(policy, backend)
        key = CacheKey.from_tokens("model", (1, 2, 3))
        old_payload = object()
        self.assertTrue(coordinator.admit_entry(key, old_payload, role="active", nbytes=50))
        before = policy.capture_state()
        backend_before = backend.values[key]
        backend.fail_insert = True
        with self.assertRaises(RuntimeError):
            coordinator.admit_entry(key, object(), role="active", nbytes=70)
        self.assertEqual(policy.capture_state(), before)
        self.assertIs(backend.values[key][0], backend_before[0])
        self.assertEqual(backend.values[key][1], backend_before[1])

    def test_nontrimmable_exact_hit_replays_one_token(self) -> None:
        prompt = [10, 20, 30]
        shorter_cache = object()

        def fetch_shorter(tokens):
            self.assertEqual(list(tokens), [10, 20])
            return shorter_cache, []

        resolved_cache, rest = cache.ensure_generation_safe_exact_hit(
            object(),
            [],
            prompt,
            can_trim=lambda _cache: False,
            trim_one=lambda _cache: self.fail("non-trimmable cache must not trim"),
            fetch_shorter=fetch_shorter,
        )
        self.assertIs(resolved_cache, shorter_cache)
        self.assertEqual(rest, [30])
        self.assertTrue(cache.is_generation_safe_hybrid_checkpoint([10, 20], prompt))


if __name__ == "__main__":
    unittest.main()
