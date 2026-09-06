import importlib
import threading
import unittest
from typing import Any, cast

import statebraid.adapters as adapters
from statebraid.adapters.mlx import (
    MLXPromptCacheBackend,
    MLXStateBraidPromptCache,
    generation_safe_prompt_cache_hit,
)
from statebraid.cache.policy import CacheCoordinator, CacheKey, WorkingSetPolicy


class FakeStorage:
    def __init__(self):
        self.rows = {}

    def capture(self, model, tokens):
        return self.rows.get((model, tuple(tokens)))

    def restore(self, model, tokens, snapshot):
        self.rows[(model, tuple(tokens))] = snapshot

    def remove(self, model, tokens):
        self.rows.pop((model, tuple(tokens)), None)

    def insert(self, model, tokens, payload, *, cache_type):
        self.rows[(model, tuple(tokens))] = (payload, cache_type)


class FakePromptCache:
    def __init__(self):
        self.storage = FakeStorage()
        self.rows = self.storage.rows

    def transactional_storage(self):
        return self.storage

    def fetch_nearest_cache(self, model, tokens):
        exact = self.rows.get((model, tuple(tokens)))
        if exact is not None:
            return exact[0], []
        for end in range(len(tokens) - 1, 0, -1):
            row = self.rows.get((model, tuple(tokens[:end])))
            if row is not None:
                return row[0], tokens[end:]
        return None, tokens


class MLXAdapterContractTest(unittest.TestCase):
    def test_managed_cache_is_part_of_public_adapter_exports(self):
        self.assertIn("MLXStateBraidPromptCache", adapters.__all__)
        self.assertIs(adapters.MLXStateBraidPromptCache, MLXStateBraidPromptCache)

    def test_maps_cache_key_without_private_backend_access(self):
        cache = FakePromptCache()
        backend = MLXPromptCacheBackend(cache)
        key = CacheKey.from_tokens("model-a", [1, 2, 3])
        payload = object()
        backend.insert(key, payload, role="stable")
        self.assertEqual(cache.storage.rows[("model-a", (1, 2, 3))], (payload, "stable"))
        snap = backend.capture(key)
        backend.remove(key)
        self.assertNotIn(("model-a", (1, 2, 3)), cache.storage.rows)
        backend.restore(key, snap)
        self.assertEqual(cache.storage.rows[("model-a", (1, 2, 3))], snap)

    def test_rejects_cache_without_transactional_capability(self):
        with self.assertRaisesRegex(TypeError, "transactional_storage"):
            MLXPromptCacheBackend(object())

    def test_managed_cache_assigns_hit_to_actual_prefix(self):
        cache = FakePromptCache()
        managed = MLXStateBraidPromptCache(
            cache, max_sequences=4, max_bytes=1_000
        )
        payload = [TinyKV(40)]
        self.assertTrue(managed.insert_cache("m", [1, 2], payload, cache_type="stable"))
        got, rest = managed.fetch_nearest_cache("m", [1, 2, 3, 4])
        self.assertIs(got, payload)
        self.assertEqual(rest, [3, 4])
        key = CacheKey.from_tokens("m", [1, 2])
        entry = managed.policy.entry(key)
        self.assertIsNotNone(entry)
        if entry is None:
            self.fail("stable entry disappeared")
        self.assertEqual(entry.hits, 1)

    def test_managed_cache_keeps_stable_and_active_lanes(self):
        cache = FakePromptCache()
        managed = MLXStateBraidPromptCache(
            cache, max_sequences=2, max_bytes=1_000
        )
        stable = [TinyKV(40)]
        active = [TinyKV(60)]
        self.assertTrue(managed.insert_stable_candidate("m", [1, 2], stable))
        self.assertTrue(
            managed.insert_active_successor(
                "m", [1, 2, 3], active, predecessor_tokens=[1, 2]
            )
        )
        self.assertEqual(set(managed.stats_by_type()), {"stable", "active"})
        self.assertEqual(managed.activation_stats()["mode"], "statebraid")
        self.assertEqual(len(managed), 2)

    def test_legacy_semantic_cache_types_do_not_gain_pin_authority(self):
        managed = MLXStateBraidPromptCache(
            FakePromptCache(), max_sequences=3, max_bytes=1_000
        )
        self.assertTrue(
            managed.insert_cache("m", [10], [TinyKV(40)], cache_type="goal")
        )
        self.assertTrue(
            managed.insert_cache("m", [11], [TinyKV(40)], cache_type="evidence")
        )
        self.assertTrue(managed.insert_stable_candidate("m", [12], [TinyKV(40)]))
        self.assertTrue(
            managed.insert_active_successor(
                "m", [12, 1], [TinyKV(40)], predecessor_tokens=[12]
            )
        )

        snapshot = managed.policy.capture_state()
        self.assertTrue(all(not entry.pinned for entry in snapshot.entries.values()))
        self.assertIsNone(managed.policy.entry(CacheKey.from_tokens("m", [10])))
        self.assertIsNotNone(managed.policy.entry(CacheKey.from_tokens("m", [12])))
        self.assertIsNotNone(managed.policy.entry(CacheKey.from_tokens("m", [12, 1])))

    def test_managed_cache_rejects_opaque_payload_without_nbytes(self):
        managed = MLXStateBraidPromptCache(
            FakePromptCache(), max_sequences=2, max_bytes=1_000
        )
        with self.assertRaisesRegex(TypeError, "nbytes"):
            managed.insert_cache("m", [1], object())


class TinyKV:
    def __init__(self, nbytes=100):
        self.nbytes = nbytes

    def is_trimmable(self):
        return False


class MLXRealStorageParityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cache_module = importlib.import_module("mlx_lm.models.cache")
            cls.cache_type = cache_module.LRUPromptCache
        except (ImportError, AttributeError) as exc:
            raise unittest.SkipTest(f"compatible mlx-lm not installed: {exc}")

    def test_statebraid_policy_owns_capacity_on_real_mlx_storage(self):
        cache = self.cache_type(max_size=1, max_bytes=1)
        backend = MLXPromptCacheBackend(cache)
        policy = WorkingSetPolicy(max_sequences=2, max_bytes=500)
        coordinator = CacheCoordinator(policy, backend)
        stable = CacheKey.from_tokens("m", [1, 2])
        active = CacheKey.from_tokens("m", [1, 2, 3])
        self.assertTrue(
            coordinator.admit_entry(stable, [TinyKV(50)], role="stable", nbytes=50)
        )
        self.assertTrue(
            coordinator.admit_entry(active, [TinyKV(70)], role="active", nbytes=70)
        )
        self.assertEqual(policy.n_sequences, 2)
        self.assertEqual(len(cache), 2)  # native max_size=1 is intentionally bypassed
        self.assertIsNotNone(cache.fetch_nearest_cache("m", [1, 2])[0])
        self.assertIsNotNone(cache.fetch_nearest_cache("m", [1, 2, 3])[0])

    def test_real_mlx_exact_hit_replays_from_n_minus_one_checkpoint(self):
        cache = self.cache_type(max_size=1, max_bytes=1)
        backend = MLXPromptCacheBackend(cache)
        policy = WorkingSetPolicy(max_sequences=2, max_bytes=500)
        coordinator = CacheCoordinator(policy, backend)
        prelast = CacheKey.from_tokens("m", [1, 2])
        exact = CacheKey.from_tokens("m", [1, 2, 3])
        self.assertTrue(
            coordinator.admit_entry(prelast, [TinyKV(50)], role="stable", nbytes=50)
        )
        self.assertTrue(
            coordinator.admit_entry(exact, [TinyKV(70)], role="active", nbytes=70)
        )
        exact_cache, rest = cache.fetch_nearest_cache("m", [1, 2, 3])
        self.assertIsNotNone(exact_cache)
        self.assertEqual(rest, [])
        safe_cache, safe_rest = generation_safe_prompt_cache_hit(
            cache, "m", [1, 2, 3], exact_cache, rest
        )
        self.assertIsNotNone(safe_cache)
        self.assertEqual(safe_rest, [3])

    def test_real_mlx_storage_concurrent_coordinator_mutation_is_consistent(self):
        cache = self.cache_type(max_size=1, max_bytes=1)
        backend = MLXPromptCacheBackend(cache)
        policy = WorkingSetPolicy(max_sequences=6, max_bytes=1_000)
        coordinator = CacheCoordinator(policy, backend)
        errors: list[BaseException] = []

        def worker(namespace: str, base: int) -> None:
            try:
                previous = None
                for i in range(20):
                    key = CacheKey.from_tokens(namespace, [base, i])
                    coordinator.admit_entry(
                        key,
                        [TinyKV(20)],
                        role="active",
                        nbytes=20,
                        predecessor=previous,
                    )
                    previous = key
                    if i % 5 == 0:
                        coordinator.trim_to(n_sequences=6)
            except BaseException as exc:  # pragma: no cover - assertion path
                errors.append(exc)

        threads = [
            threading.Thread(target=worker, args=("m-a", 10)),
            threading.Thread(target=worker, args=("m-b", 20)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(errors, [])
        self.assertEqual(policy.n_sequences, len(cache))
        self.assertEqual(policy.nbytes, cache.nbytes)
        self.assertLessEqual(policy.n_sequences, 6)

    def test_real_mlx_storage_rolls_back_after_failed_successor_insert(self):
        cache = self.cache_type(max_size=1, max_bytes=1)
        backend = MLXPromptCacheBackend(cache)
        policy = WorkingSetPolicy(max_sequences=2, max_bytes=500)
        coordinator = CacheCoordinator(policy, backend)
        old = CacheKey.from_tokens("m", [1, 2])
        new = CacheKey.from_tokens("m", [1, 2, 3])
        self.assertTrue(
            coordinator.admit_entry(old, [TinyKV(50)], role="active", nbytes=50)
        )
        storage = cast(Any, backend._storage)
        original_insert = storage.insert

        def fail_insert(*args, **kwargs):
            raise RuntimeError("injected MLX storage failure")

        storage.insert = fail_insert
        try:
            with self.assertRaisesRegex(RuntimeError, "injected MLX"):
                coordinator.admit_entry(
                    new,
                    [TinyKV(70)],
                    role="active",
                    nbytes=70,
                    predecessor=old,
                )
        finally:
            storage.insert = original_insert
        self.assertIsNotNone(backend.capture(old))
        self.assertIsNone(backend.capture(new))
        self.assertIsNotNone(policy.entry(old))
        self.assertIsNone(policy.entry(new))


if __name__ == "__main__":
    unittest.main(verbosity=2)
