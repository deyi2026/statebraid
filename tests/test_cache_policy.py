import threading
import unittest
from typing import Any

from statebraid.cache.policy import (
    CacheCoordinator,
    CacheKey,
    WorkingSetPolicy,
    matched_prefix_key,
)


def key(token, *tail):
    return CacheKey.from_tokens("model-a", (token, *tail))


class FakeBackend:
    def __init__(self):
        self.values: dict[CacheKey, tuple[object, str]] = {}
        self.fail_next_insert = False

    def capture(self, key: CacheKey) -> Any:
        return self.values.get(key)

    def restore(self, key: CacheKey, snapshot: Any) -> None:
        self.values[key] = snapshot

    def remove(self, key: CacheKey) -> None:
        self.values.pop(key, None)

    def insert(self, key: CacheKey, payload: object, *, role: str) -> None:
        self.values[key] = (payload, role)
        if self.fail_next_insert:
            self.fail_next_insert = False
            raise RuntimeError("injected backend failure")


class WorkingSetPolicyTest(unittest.TestCase):
    def setUp(self):
        self.policy = WorkingSetPolicy(max_sequences=4, max_bytes=400)
        self.backend = FakeBackend()
        self.coordinator = CacheCoordinator(self.policy, self.backend)

    def admit(self, cache_key, role, nbytes=100, predecessor=None, payload=None):
        plan = self.policy.plan_admission(cache_key, role=role, nbytes=nbytes, predecessor=predecessor)
        self.assertTrue(plan.accepted, plan)
        self.coordinator.admit(plan, payload if payload is not None else object())
        return plan

    def test_pin_saturation_reserves_two_transient_slots(self):
        self.admit(key(1), "goal")
        self.admit(key(2), "evidence")
        self.admit(key(3), "rules")
        self.admit(key(4), "system")
        self.admit(key(5), "active")
        snap = self.policy.snapshot()
        self.assertEqual(snap["transient_reserve"], 2)
        self.assertEqual(snap["pin_limit"], 2)
        self.assertEqual(self.policy.n_sequences, 4)
        self.assertGreaterEqual(self.policy.pin_quota_evictions, 1)
        self.assertIsNotNone(self.policy.entry(key(5)))

    def test_stable_lane_rotates_without_removing_active(self):
        self.admit(key(1), "goal")
        self.admit(key(2), "evidence")
        stable1 = key(10)
        active = key(10, 1)
        self.admit(stable1, "stable", nbytes=50)
        self.admit(active, "active", nbytes=100)
        stable2 = key(20)
        plan = self.admit(stable2, "stable", nbytes=50)
        self.assertIn("stable_rotate", {ev.reason for ev in plan.evictions})
        self.assertIsNone(self.policy.entry(stable1))
        self.assertIsNotNone(self.policy.entry(active))
        self.assertIsNotNone(self.policy.entry(stable2))

    def test_active_successor_compacts_only_actual_prefix_lineage(self):
        base = key(1, 2, 3)
        other = key(9, 9)
        self.admit(base, "active")
        self.admit(other, "active")
        successor = key(1, 2, 3, 4)
        plan = self.admit(successor, "active", predecessor=base)
        self.assertIn("active_successor", {ev.reason for ev in plan.evictions})
        self.assertIsNone(self.policy.entry(base))
        self.assertIsNotNone(self.policy.entry(other))
        self.assertIsNotNone(self.policy.entry(successor))
        self.assertEqual(self.policy.active_successor_evictions, 1)

    def test_byte_pressure_preserves_fitting_stable_active_pair(self):
        policy = WorkingSetPolicy(max_sequences=8, max_bytes=250)
        backend = FakeBackend()
        coordinator = CacheCoordinator(policy, backend)

        def admit_local(cache_key, role, nbytes):
            plan = policy.plan_admission(cache_key, role=role, nbytes=nbytes)
            self.assertTrue(plan.accepted)
            coordinator.admit(plan, object())

        admit_local(key(1), "goal", 100)
        admit_local(key(2), "goal", 100)
        stable = key(7)
        active = key(7, 1)
        admit_local(stable, "stable", 50)
        admit_local(active, "active", 100)
        self.assertIsNotNone(policy.entry(stable))
        self.assertIsNotNone(policy.entry(active))
        self.assertLessEqual(policy.nbytes, 250)
        self.assertEqual(sum(entry.pinned for entry in policy.capture_state().entries.values()), 1)

    def test_stable_candidate_uses_reuse_not_semantics(self):
        title = CacheKey.from_tokens("model-a", [7] * 8)
        main = CacheKey.from_tokens("model-a", [8] * 64)
        first = self.policy.plan_stable_candidate(title, nbytes=50)
        self.coordinator.admit(first, object())
        larger = self.policy.plan_stable_candidate(main, nbytes=50)
        self.assertTrue(larger.accepted)
        self.coordinator.admit(larger, object())
        self.assertTrue(self.policy.observe_hit(main))
        helper_once = self.policy.plan_stable_candidate(title, nbytes=50)
        self.assertFalse(helper_once.accepted)
        self.assertEqual(helper_once.reason, "stable_probation")
        self.assertTrue(self.policy.observe_hit(main))
        helper_again = self.policy.plan_stable_candidate(title, nbytes=50)
        self.assertFalse(helper_again.accepted)
        self.assertIsNotNone(self.policy.entry(main))

    def test_backend_failure_restores_policy_and_payload_refs(self):
        stable = key(1, 2)
        original_payload = object()
        self.admit(stable, "stable", nbytes=50, payload=original_payload)
        before = self.policy.snapshot()
        original_backend = dict(self.backend.values)

        replacement = key(3, 4)
        plan = self.policy.plan_admission(replacement, role="stable", nbytes=60)
        self.backend.fail_next_insert = True
        with self.assertRaisesRegex(RuntimeError, "injected"):
            self.coordinator.admit(plan, object())

        self.assertEqual(self.policy.snapshot(), before)
        self.assertEqual(self.backend.values, original_backend)
        self.assertIs(self.backend.values[stable][0], original_payload)

    def test_oversized_candidate_is_rejected_without_rotation(self):
        stable = key(1)
        self.admit(stable, "stable", nbytes=50)
        before = self.policy.snapshot()
        plan = self.policy.plan_stable_candidate(key(2), nbytes=1000)
        self.assertFalse(plan.accepted)
        self.assertEqual(self.policy.snapshot(), before)

    def test_trim_preserves_working_pair_when_it_fits(self):
        policy = WorkingSetPolicy(max_sequences=8, max_bytes=800)
        backend = FakeBackend()
        coordinator = CacheCoordinator(policy, backend)

        def admit_local(cache_key, role, nbytes=100):
            plan = policy.plan_admission(cache_key, role=role, nbytes=nbytes)
            self.assertTrue(plan.accepted)
            coordinator.admit(plan, object())

        for i in range(4):
            admit_local(key(30 + i), "goal")
        stable = key(40)
        active = key(40, 1)
        admit_local(stable, "stable", 50)
        admit_local(active, "active", 100)
        trim = policy.plan_trim(n_bytes=150)
        self.assertTrue(coordinator.trim(trim))
        self.assertIsNotNone(policy.entry(stable))
        self.assertIsNotNone(policy.entry(active))
        self.assertEqual(policy.nbytes, 150)

        trim_all = policy.plan_trim(n_bytes=40)
        self.assertTrue(coordinator.trim(trim_all))
        self.assertLessEqual(policy.nbytes, 40)

    def test_trim_backend_failure_restores_state(self):
        class FailingRemoveBackend(FakeBackend):
            def __init__(self):
                super().__init__()
                self.remove_calls = 0
                self.fail_on_remove_call: int | None = None

            def remove(self, key: CacheKey) -> None:
                self.remove_calls += 1
                if self.remove_calls == self.fail_on_remove_call:
                    raise RuntimeError("injected remove failure")
                super().remove(key)

        policy = WorkingSetPolicy(max_sequences=4, max_bytes=400)
        backend = FailingRemoveBackend()
        coordinator = CacheCoordinator(policy, backend)
        for i in range(3):
            plan = policy.plan_admission(key(50 + i), role="system", nbytes=100)
            coordinator.admit(plan, object())
        before_policy = policy.snapshot()
        before_backend = dict(backend.values)
        trim = policy.plan_trim(n_sequences=1)
        backend.fail_on_remove_call = backend.remove_calls + 2
        with self.assertRaisesRegex(RuntimeError, "injected remove"):
            coordinator.trim(trim)
        self.assertEqual(policy.snapshot(), before_policy)
        self.assertEqual(backend.values, before_backend)

    def test_repeated_stable_promotion_counts_only_after_commit(self):
        incumbent = CacheKey.from_tokens("model-a", [1] * 64)
        candidate = CacheKey.from_tokens("model-a", [2] * 16)
        first = self.policy.plan_stable_candidate(incumbent, nbytes=50)
        self.coordinator.admit(first, object())
        self.policy.observe_hit(incumbent)
        self.assertFalse(self.policy.plan_stable_candidate(candidate, nbytes=50).accepted)
        promote = self.policy.plan_stable_candidate(candidate, nbytes=50)
        self.assertTrue(promote.accepted)
        self.assertEqual(self.policy.stable_candidate_promotions, 0)
        self.coordinator.admit(promote, object())
        self.assertEqual(self.policy.stable_candidate_promotions, 1)
        self.assertIsNotNone(self.policy.entry(candidate))

    def test_transaction_snapshot_does_not_deepcopy_namespace(self):
        class NoDeepcopyNamespace:
            def __hash__(self):
                return id(self)

            def __deepcopy__(self, memo):
                raise AssertionError("namespace must remain an opaque reference")

        namespace = NoDeepcopyNamespace()
        cache_key = CacheKey.from_tokens(namespace, [1, 2, 3])
        plan = self.policy.plan_admission(cache_key, role="stable", nbytes=50)
        self.assertTrue(self.coordinator.admit(plan, object()))
        snapshot = self.policy.capture_state()
        self.assertIn(cache_key, snapshot.entries)

    def test_coordinator_serializes_concurrent_admit_and_trim(self):
        policy = WorkingSetPolicy(max_sequences=8, max_bytes=800)
        backend = FakeBackend()
        coordinator = CacheCoordinator(policy, backend)
        errors = []

        def worker(worker_id):
            try:
                for i in range(80):
                    cache_key = CacheKey.from_tokens(
                        "model-a", [worker_id, i, worker_id + i]
                    )
                    coordinator.admit_entry(
                        cache_key, object(), role=("goal" if i % 9 == 0 else "active"), nbytes=50
                    )
                    if i % 17 == 0:
                        coordinator.trim_to(n_sequences=6, n_bytes=500)
            except Exception as exc:  # pragma: no cover - assertion reports details
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(6)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(errors, [])
        self.assertLessEqual(policy.n_sequences, policy.max_sequences)
        self.assertLessEqual(policy.nbytes, policy.max_bytes)
        self.assertEqual(set(backend.values), set(policy.capture_state().entries))

    def test_hit_credit_uses_actual_matched_prefix(self):
        stable = CacheKey.from_tokens("model-a", [1, 2, 3])
        self.admit(stable, "stable", nbytes=50)
        prompt = [1, 2, 3, 9, 10]
        actual = matched_prefix_key("model-a", prompt, [9, 10])
        self.assertEqual(actual, stable)
        if actual is None:
            self.fail("expected a matched prefix key")
        self.assertTrue(self.coordinator.observe_hit(actual))
        entry = self.policy.entry(stable)
        if entry is None:
            self.fail("stable entry disappeared")
        self.assertEqual(entry.hits, 1)

    def test_capacity_evicts_low_rank_before_pin_and_working_state(self):
        policy = WorkingSetPolicy(max_sequences=4, max_bytes=400)
        backend = FakeBackend()
        coordinator = CacheCoordinator(policy, backend)
        goal = key(60)
        assistant = key(61)
        system = key(62)
        stable = key(63)
        coordinator.admit_entry(goal, object(), role="goal", nbytes=100)
        coordinator.admit_entry(assistant, object(), role="assistant", nbytes=100)
        coordinator.admit_entry(system, object(), role="system", nbytes=100)
        coordinator.admit_entry(stable, object(), role="stable", nbytes=100)
        active = key(63, 1)
        coordinator.admit_entry(active, object(), role="active", nbytes=100)
        self.assertIsNone(policy.entry(assistant))
        self.assertIsNotNone(policy.entry(goal))
        self.assertIsNotNone(policy.entry(stable))
        self.assertIsNotNone(policy.entry(active))


if __name__ == "__main__":
    unittest.main()
