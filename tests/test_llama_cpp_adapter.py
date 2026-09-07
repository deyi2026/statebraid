import unittest

from statebraid.adapters.llama_cpp import (
    LLAMA_CPP_BACKEND_DESCRIPTOR,
    LLAMA_CPP_REFERENCE_SHA,
    LlamaCppHTTPAdapter,
    LlamaCppReuseHandle,
    llama_cpp_cache_namespace,
    normalize_llama_cpp_reuse,
)
from statebraid.backend import (
    BackendCapability,
    PrefixLookupBackend,
    UnsupportedBackendCapability,
)


class FakeTransport:
    def __init__(self):
        self.get_result = [{"id": 0, "is_processing": False}]
        self.gets = []
        self.post_results = []
        self.posts = []

    def get_json(self, path):
        if path != "/slots":
            raise AssertionError(path)
        self.gets.append(path)
        return self.get_result

    def post_json(self, path, payload):
        if path != "/completion":
            raise AssertionError(path)
        self.posts.append(dict(payload))
        if not self.post_results:
            raise AssertionError("no fake response queued")
        return self.post_results.pop(0)


class LlamaCppAdapterTest(unittest.TestCase):
    def test_descriptor_is_deliberately_partial(self):
        self.assertEqual(len(LLAMA_CPP_REFERENCE_SHA), 40)
        self.assertEqual(LLAMA_CPP_BACKEND_DESCRIPTOR.integration_level, "partial")
        self.assertEqual(
            LLAMA_CPP_BACKEND_DESCRIPTOR.capabilities,
            frozenset(
                {
                    BackendCapability.PREFIX_LOOKUP,
                    BackendCapability.HIT_ATTRIBUTION,
                    BackendCapability.GENERATION_SAFETY,
                }
            ),
        )
        self.assertFalse(
            LLAMA_CPP_BACKEND_DESCRIPTOR.supports(
                BackendCapability.NAMESPACE_ISOLATION,
                BackendCapability.ADMISSION_RESIDENCY,
                BackendCapability.TRANSACTIONAL_MUTATION,
                BackendCapability.ROLLBACK,
            )
        )

    def test_normalizes_actual_served_prefix(self):
        response = {"timings": {"cache_n": 2, "prompt_n": 2}}
        observation = normalize_llama_cpp_reuse(
            backend_identity="http://example",
            id_slot=3,
            prompt_tokens=[10, 11, 12, 13],
            response=response,
        )
        self.assertEqual(observation.matched_tokens, 2)
        self.assertEqual(observation.remaining, (12, 13))
        assert observation.matched_key is not None
        self.assertEqual(observation.matched_key.tokens, (10, 11))
        self.assertIsInstance(observation.payload, LlamaCppReuseHandle)
        assert isinstance(observation.payload, LlamaCppReuseHandle)
        self.assertEqual(
            observation.namespace,
            ("llama.cpp", "http://example", "local-default"),
        )
        self.assertEqual(observation.payload.id_slot, 3)

    def test_cold_observation_has_no_false_payload(self):
        observation = normalize_llama_cpp_reuse(
            backend_identity="http://example",
            id_slot=0,
            prompt_tokens=[1, 2, 3],
            response={"timings": {"cache_n": 0, "prompt_n": 3}},
        )
        self.assertFalse(observation.hit)
        self.assertEqual(observation.remaining, (1, 2, 3))
        self.assertIsNone(observation.payload)

    def test_rejects_invalid_backend_timings(self):
        with self.assertRaisesRegex(ValueError, "outside prompt length"):
            normalize_llama_cpp_reuse(
                backend_identity="x",
                id_slot=0,
                prompt_tokens=[1, 2],
                response={"timings": {"cache_n": 4, "prompt_n": 0}},
            )
        with self.assertRaisesRegex(ValueError, "missing timings"):
            normalize_llama_cpp_reuse(
                backend_identity="x",
                id_slot=0,
                prompt_tokens=[1],
                response={},
            )
        with self.assertRaisesRegex(ValueError, "timing evidence is inconsistent"):
            normalize_llama_cpp_reuse(
                backend_identity="x",
                id_slot=0,
                prompt_tokens=[1, 2, 3],
                response={"timings": {"cache_n": 1, "prompt_n": 1}},
            )

    def test_http_adapter_is_single_domain_fail_closed(self):
        transport = FakeTransport()
        with self.assertRaises(UnsupportedBackendCapability):
            LlamaCppHTTPAdapter(transport=transport, trust_domain="tenant-a")
        self.assertEqual(transport.posts, [])

    def test_http_adapter_matches_prefix_lookup_protocol_shape(self):
        adapter = LlamaCppHTTPAdapter(transport=FakeTransport())
        backend: PrefixLookupBackend = adapter
        self.assertIs(backend, adapter)
        self.assertEqual(
            adapter.namespace, llama_cpp_cache_namespace("http://127.0.0.1:8080")
        )

    def test_http_adapter_rejects_upstream_slot_wrapping(self):
        transport = FakeTransport()
        transport.get_result = [{"id": 0}, {"id": 1}]
        adapter = LlamaCppHTTPAdapter(id_slot=3, transport=transport)
        with self.assertRaisesRegex(ValueError, "modulo slot wrapping"):
            adapter.lookup(adapter.namespace, [1, 2, 3])
        self.assertEqual(transport.posts, [])

    def test_http_adapter_posts_bounded_completion_probe(self):
        transport = FakeTransport()
        transport.post_results.append(
            {"timings": {"cache_n": 2, "prompt_n": 1}}
        )
        transport.get_result = [{"id": 0}, {"id": 2}]
        adapter = LlamaCppHTTPAdapter(
            "http://llama.local:8080", id_slot=2, transport=transport
        )
        observation = adapter.lookup(adapter.namespace, [5, 6, 7])
        self.assertEqual(observation.matched_tokens, 2)
        self.assertEqual(
            transport.posts,
            [
                {
                    "prompt": [5, 6, 7],
                    "id_slot": 2,
                    "cache_prompt": True,
                    "n_cache_reuse": 0,
                    "n_predict": 0,
                    "stream": False,
                }
            ],
        )

    def test_generation_safe_exact_accepts_replay_or_full_recompute(self):
        transport = FakeTransport()
        transport.post_results.extend(
            [
                {"timings": {"cache_n": 2, "prompt_n": 1}},
                {"timings": {"cache_n": 0, "prompt_n": 4}},
                {"timings": {"cache_n": 4, "prompt_n": 0}},
            ]
        )
        adapter = LlamaCppHTTPAdapter(transport=transport)
        safe = adapter.generation_safe_exact(adapter.namespace, [7, 8, 9])
        self.assertEqual(safe.matched_tokens, 2)
        recompute = adapter.generation_safe_exact(
            adapter.namespace, [7, 8, 9, 10]
        )
        self.assertFalse(recompute.hit)
        self.assertEqual(recompute.remaining, (7, 8, 9, 10))
        with self.assertRaisesRegex(ValueError, "empty generation input"):
            adapter.generation_safe_exact(adapter.namespace, [7, 8, 9, 10])


if __name__ == "__main__":
    unittest.main()
