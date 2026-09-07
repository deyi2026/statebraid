import unittest

from statebraid.adapters.llama_cpp_managed import (
    LLAMA_CPP_MANAGED_BACKEND_DESCRIPTOR,
    LLAMA_CPP_MANAGED_REFERENCE_SHA,
    LlamaCppManagedHTTPAdapter,
    LlamaCppManagedStateHandle,
    LlamaCppStateBraidPromptCache,
    llama_cpp_managed_reference_source_match,
)
from statebraid.backend import BackendCapability, UnsupportedBackendCapability


class FakeManagedTransport:
    def __init__(self):
        self.epoch = "0123456789abcdef0123456789abcdef"
        self.props = {
            "build_info": f"b3-{LLAMA_CPP_MANAGED_REFERENCE_SHA[:10]}",
            "total_slots": 1,
        }
        self.slots = [{"id": 0, "is_processing": False}]
        self.handles = {}
        self.capture_queue = []
        self.completion_queue = []
        self.actions = []
        self.next_handle = 1
        self.n_cleared = 0
        self.drop_failures_before_apply = 0
        self.drop_response_loss_after_apply = False

    def get_json(self, path):
        if path == "/props":
            return dict(self.props)
        if path == "/slots":
            return [dict(item) for item in self.slots]
        if path == "/statebraid/cache":
            rows = [
                {
                    "handle": handle,
                    "n_tokens": values[0],
                    "n_bytes": values[1],
                }
                for handle, values in sorted(self.handles.items())
            ]
            return {
                "enabled": True,
                "epoch": self.epoch,
                "n_handles": len(rows),
                "n_tokens": sum(row["n_tokens"] for row in rows),
                "n_bytes": sum(row["n_bytes"] for row in rows),
                "handles": rows,
            }
        raise AssertionError(path)

    def post_json(self, path, payload):
        payload = dict(payload)
        if path == "/completion":
            self.actions.append(("completion", payload))
            if not self.completion_queue:
                raise AssertionError("no completion response queued")
            return self.completion_queue.pop(0)
        if path != "/statebraid/cache":
            raise AssertionError(path)

        action = payload["action"]
        self.actions.append((action, payload))
        if payload["epoch"] != self.epoch:
            raise AssertionError("test transport received stale epoch")

        if action == "clear":
            result = {
                "success": True,
                "epoch": self.epoch,
                "id_slot": payload["id_slot"],
                "n_cleared": self.n_cleared,
            }
            self.n_cleared = 0
            return result

        if action == "capture":
            if not self.capture_queue:
                raise AssertionError("no capture accounting queued")
            n_tokens, n_bytes = self.capture_queue.pop(0)
            handle = f"sbm1-{self.next_handle:016x}"
            self.next_handle += 1
            self.handles[handle] = (n_tokens, n_bytes)
            self.n_cleared = n_tokens
            return {
                "success": True,
                "epoch": self.epoch,
                "handle": handle,
                "id_slot": payload["id_slot"],
                "n_tokens": n_tokens,
                "n_bytes": n_bytes,
            }

        handle = payload["handle"]
        if handle not in self.handles:
            raise AssertionError(f"unknown fake handle: {handle}")
        n_tokens, n_bytes = self.handles[handle]
        if action == "restore":
            self.n_cleared = n_tokens
            return {
                "success": True,
                "epoch": self.epoch,
                "handle": handle,
                "id_slot": payload["id_slot"],
                "n_tokens": n_tokens,
                "n_bytes": n_bytes,
            }
        if action == "drop":
            if self.drop_failures_before_apply > 0:
                self.drop_failures_before_apply -= 1
                raise OSError("injected pre-apply drop failure")
            del self.handles[handle]
            if self.drop_response_loss_after_apply:
                self.drop_response_loss_after_apply = False
                raise OSError("injected response loss after drop")
            return {
                "success": True,
                "epoch": self.epoch,
                "handle": handle,
                "n_tokens": n_tokens,
                "n_bytes": n_bytes,
            }
        raise AssertionError(action)


class LlamaCppManagedAdapterTest(unittest.TestCase):
    def adapter(self, transport=None):
        return LlamaCppManagedHTTPAdapter(
            "http://llama-managed.local:8080",
            id_slot=0,
            transport=transport or FakeManagedTransport(),
        )

    def test_descriptor_declares_managed_mechanics_without_namespace_claim(self):
        descriptor = LLAMA_CPP_MANAGED_BACKEND_DESCRIPTOR
        self.assertTrue(
            descriptor.supports(
                BackendCapability.ADMISSION_RESIDENCY,
                BackendCapability.TRANSACTIONAL_MUTATION,
                BackendCapability.PREFIX_LOOKUP,
                BackendCapability.HIT_ATTRIBUTION,
                BackendCapability.GENERATION_SAFETY,
            )
        )
        self.assertFalse(descriptor.supports(BackendCapability.NAMESPACE_ISOLATION))
        self.assertFalse(descriptor.supports(BackendCapability.ROLLBACK))
        self.assertFalse(descriptor.qualification_profile.runtime_qualified)
        self.assertEqual(descriptor.integration_level, "partial")

    def test_managed_source_is_distinct_from_stock_reference(self):
        self.assertTrue(
            llama_cpp_managed_reference_source_match(
                f"b3-{LLAMA_CPP_MANAGED_REFERENCE_SHA[:10]}"
            )
        )
        self.assertFalse(llama_cpp_managed_reference_source_match("b1-465e49b9c"))

    def test_preflight_rejects_wrong_source_and_non_default_domain(self):
        transport = FakeManagedTransport()
        transport.props["build_info"] = "b3-deadbeef"
        with self.assertRaisesRegex(UnsupportedBackendCapability, "managed M1"):
            self.adapter(transport)

        with self.assertRaises(UnsupportedBackendCapability):
            LlamaCppManagedHTTPAdapter(
                transport=FakeManagedTransport(), trust_domain="tenant-a"
            )

    def test_low_level_handle_lifecycle_and_epoch_binding(self):
        transport = FakeManagedTransport()
        adapter = self.adapter(transport)
        transport.capture_queue.append((3, 100))
        state = adapter.capture_current_state()
        self.assertEqual(state.n_tokens, 3)
        self.assertEqual(state.nbytes, 100)
        self.assertEqual(adapter.clear_live_slot(), 3)
        adapter.restore_state(state)
        self.assertEqual(len(transport.handles), 1)
        transport.drop_response_loss_after_apply = True
        adapter.drop_state(state)
        self.assertEqual(len(transport.handles), 0)

        transport.epoch = "fedcba9876543210fedcba9876543210"
        with self.assertRaisesRegex(UnsupportedBackendCapability, "epoch changed"):
            adapter.managed_store()

    def test_active_successor_commits_policy_and_physical_eviction(self):
        transport = FakeManagedTransport()
        cache = LlamaCppStateBraidPromptCache(
            self.adapter(transport), max_sequences=3, max_bytes=1000
        )
        transport.capture_queue.extend([(3, 100), (4, 120)])

        self.assertTrue(cache.capture_and_admit([1, 2, 3], role="active"))
        first_handle = next(iter(transport.handles))
        self.assertTrue(
            cache.capture_and_admit(
                [1, 2, 3, 4],
                role="active",
                predecessor_tokens=[1, 2, 3],
            )
        )
        self.assertNotIn(first_handle, transport.handles)
        self.assertEqual(len(transport.handles), 1)
        self.assertEqual(cache.policy.n_sequences, 1)
        self.assertEqual(cache.policy.active_successor_evictions, 1)
        cache.backend.assert_physical_matches_registry()

    def test_rejected_admission_drops_unbound_remote_handle(self):
        transport = FakeManagedTransport()
        cache = LlamaCppStateBraidPromptCache(
            self.adapter(transport), max_sequences=1, max_bytes=100
        )
        transport.capture_queue.append((2, 150))
        self.assertFalse(cache.capture_and_admit([7, 8], role="active"))
        self.assertEqual(transport.handles, {})
        self.assertEqual(cache.policy.n_sequences, 0)

    def test_capture_token_mismatch_drops_remote_handle(self):
        transport = FakeManagedTransport()
        cache = LlamaCppStateBraidPromptCache(
            self.adapter(transport), max_sequences=2, max_bytes=1000
        )
        transport.capture_queue.append((4, 100))
        with self.assertRaisesRegex(ValueError, "token count"):
            cache.capture_current([1, 2, 3])
        self.assertEqual(transport.handles, {})

    def test_prepare_clears_live_slot_then_restores_best_resident_handle(self):
        transport = FakeManagedTransport()
        cache = LlamaCppStateBraidPromptCache(
            self.adapter(transport), max_sequences=3, max_bytes=1000
        )
        transport.capture_queue.extend([(2, 80), (3, 90)])
        self.assertTrue(cache.capture_and_admit([1, 2], role="stable"))
        self.assertTrue(cache.capture_and_admit([1, 2, 9], role="active"))
        transport.actions.clear()

        restored = cache.prepare([1, 2, 8, 10])
        self.assertIsNotNone(restored)
        assert restored is not None
        self.assertEqual(restored.key.tokens, (1, 2))
        self.assertEqual(restored.candidate_lcp, 2)
        self.assertEqual([row[0] for row in transport.actions], ["clear", "restore"])

    def test_prepare_with_no_candidate_still_clears_live_slot(self):
        transport = FakeManagedTransport()
        cache = LlamaCppStateBraidPromptCache(
            self.adapter(transport), max_sequences=2, max_bytes=1000
        )
        transport.actions.clear()
        self.assertIsNone(cache.prepare([99, 100]))
        self.assertEqual([row[0] for row in transport.actions], ["clear"])

    def test_nonempty_unknown_remote_store_is_not_adopted(self):
        transport = FakeManagedTransport()
        transport.handles["sbm1-unknown"] = (2, 100)
        adapter = self.adapter(transport)
        with self.assertRaisesRegex(UnsupportedBackendCapability, "not empty"):
            LlamaCppStateBraidPromptCache(
                adapter, max_sequences=2, max_bytes=1000
            )

    def test_transaction_failure_rolls_back_registry_and_drops_new_orphan(self):
        transport = FakeManagedTransport()
        cache = LlamaCppStateBraidPromptCache(
            self.adapter(transport), max_sequences=2, max_bytes=1000
        )
        transport.capture_queue.extend([(2, 80), (3, 90)])
        self.assertTrue(cache.capture_and_admit([1, 2], role="active"))
        original = dict(cache.backend.records)
        original_remote = dict(transport.handles)

        state = cache.capture_current([3, 4, 5])
        real_insert = cache.backend.insert

        def fail_insert(key, payload, *, role):
            raise RuntimeError("injected insert failure")

        cache.backend.insert = fail_insert
        try:
            with self.assertRaisesRegex(RuntimeError, "injected"):
                cache.admit_captured([3, 4, 5], state, role="active")
        finally:
            cache.backend.insert = real_insert

        self.assertEqual(cache.backend.records, original)
        self.assertEqual(transport.handles, original_remote)
        cache.backend.assert_physical_matches_registry()

    def test_unresolved_physical_gc_blocks_new_capture_until_reconciled(self):
        transport = FakeManagedTransport()
        cache = LlamaCppStateBraidPromptCache(
            self.adapter(transport), max_sequences=1, max_bytes=1000
        )
        transport.capture_queue.extend([(2, 80), (2, 90), (2, 100)])
        self.assertTrue(cache.capture_and_admit([1, 2], role="active"))

        transport.drop_failures_before_apply = 2
        with self.assertRaisesRegex(OSError, "pre-apply"):
            cache.capture_and_admit([3, 4], role="active")
        self.assertEqual(cache.backend.pending_drop_count, 1)
        self.assertEqual(cache.backend.pending_drop_bytes, 80)
        self.assertEqual(len(transport.handles), 2)

        # The next capture retries physical GC before allocating a third handle.
        with self.assertRaisesRegex(OSError, "pre-apply"):
            cache.capture_current([5, 6])
        self.assertEqual(len(transport.handles), 2)
        self.assertEqual(len(transport.capture_queue), 1)

        # Once reconciliation succeeds, capture may allocate again.
        state = cache.capture_current([5, 6])
        self.assertEqual(state.nbytes, 100)
        self.assertEqual(cache.backend.pending_drop_count, 0)

    def test_managed_lookup_keeps_actual_prefix_generation_evidence(self):
        transport = FakeManagedTransport()
        transport.completion_queue.append(
            {"timings": {"cache_n": 2, "prompt_n": 1}}
        )
        adapter = self.adapter(transport)
        observation = adapter.lookup(adapter.namespace, [5, 6, 7])
        self.assertEqual(observation.matched_tokens, 2)
        self.assertEqual(observation.remaining, (7,))


if __name__ == "__main__":
    unittest.main()
