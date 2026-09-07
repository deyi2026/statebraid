import unittest
from unittest.mock import patch

from statebraid.adapters.mlx import (
    MLX_BACKEND_DESCRIPTOR,
    MLXStateBraidPromptCache,
    generation_safe_prompt_cache_hit,
)
from statebraid.backend import (
    BackendCapability,
    BackendDescriptor,
    ConformanceStatus,
    LookupObservation,
    run_backend_conformance,
)
from statebraid.cache import CacheKey, make_cache_namespace


class TinyKV:
    def __init__(self, nbytes: int):
        self.nbytes = nbytes

    def is_trimmable(self):
        return False


class FakeStorage:
    def __init__(self):
        self.rows = {}
        self.fail_insert = False

    def capture(self, model, tokens):
        return self.rows.get((model, tuple(tokens)))

    def restore(self, model, tokens, snapshot):
        self.rows[(model, tuple(tokens))] = snapshot

    def remove(self, model, tokens):
        self.rows.pop((model, tuple(tokens)), None)

    def insert(self, model, tokens, payload, *, cache_type):
        if self.fail_insert:
            self.fail_insert = False
            raise RuntimeError("injected conformance insert failure")
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


class _NonTrimmableCacheModule:
    @staticmethod
    def can_trim_prompt_cache(_cache):
        return False

    @staticmethod
    def trim_prompt_cache(_cache, _n):
        raise AssertionError("non-trimmable conformance cache must not trim")


class MLXConformanceDriver:
    descriptor = MLX_BACKEND_DESCRIPTOR

    def __init__(self, max_sequences: int, max_bytes: int):
        self.prompt_cache = FakePromptCache()
        self.managed = MLXStateBraidPromptCache(
            self.prompt_cache,
            max_sequences=max_sequences,
            max_bytes=max_bytes,
        )

    @staticmethod
    def _namespace(trust_domain: str):
        return make_cache_namespace("conformance-model", trust_domain)

    def cache_key(self, trust_domain, tokens):
        return CacheKey.from_tokens(self._namespace(trust_domain), tokens)

    def payload(self, nbytes: int) -> object:
        return [TinyKV(nbytes)]

    def seed(self, trust_domain, tokens, payload, *, role, nbytes) -> None:
        """Test-only setup; it does not assert backend admission ownership."""
        admitted = self.admit(
            trust_domain,
            tokens,
            payload,
            role=role,
            nbytes=nbytes,
        )
        if not admitted:
            raise RuntimeError("conformance seed admission failed")

    def admit(
        self,
        trust_domain,
        tokens,
        payload,
        *,
        role,
        nbytes,
        predecessor_tokens=None,
    ) -> bool:
        namespace = self._namespace(trust_domain)
        if predecessor_tokens is not None:
            return self.managed.insert_active_successor(
                namespace,
                list(tokens),
                payload,
                predecessor_tokens=predecessor_tokens,
            )
        return self.managed.insert_cache(
            namespace, list(tokens), payload, cache_type=role
        )

    def lookup(self, trust_domain, tokens) -> LookupObservation:
        namespace = self._namespace(trust_domain)
        payload, remaining = self.managed.fetch_nearest_cache(namespace, list(tokens))
        return LookupObservation.from_backend_result(
            namespace, tokens, payload, remaining
        )

    def contains(self, trust_domain, tokens) -> bool:
        key = CacheKey.from_tokens(self._namespace(trust_domain), tokens)
        return self.managed.policy.entry(key) is not None

    def entry_hits(self, trust_domain, tokens):
        key = CacheKey.from_tokens(self._namespace(trust_domain), tokens)
        entry = self.managed.policy.entry(key)
        return None if entry is None else entry.hits

    def resident_stats(self):
        return self.managed.policy.n_sequences, self.managed.policy.nbytes

    def fail_next_insert(self) -> None:
        self.prompt_cache.storage.fail_insert = True

    def generation_safe_exact(self, trust_domain, tokens) -> LookupObservation:
        namespace = self._namespace(trust_domain)
        exact_cache, rest = self.prompt_cache.fetch_nearest_cache(
            namespace, list(tokens)
        )
        with patch(
            "statebraid.adapters.mlx.importlib.import_module",
            return_value=_NonTrimmableCacheModule,
        ):
            safe_cache, safe_rest = generation_safe_prompt_cache_hit(
                self.prompt_cache,
                namespace,
                list(tokens),
                exact_cache,
                rest,
            )
        return LookupObservation.from_backend_result(
            namespace, tokens, safe_cache, safe_rest
        )


class PartialConformanceDriver(MLXConformanceDriver):
    descriptor = BackendDescriptor(
        name="partial-test-backend",
        adapter="tests.partial",
        capabilities=frozenset({BackendCapability.NAMESPACE_ISOLATION}),
    )


class ObserveGenerationConformanceDriver(MLXConformanceDriver):
    """Proves read/reuse mechanics without declaring residency ownership."""

    descriptor = BackendDescriptor(
        name="observe-generation-test-backend",
        adapter="tests.observe_generation",
        capabilities=frozenset(
            {
                BackendCapability.NAMESPACE_ISOLATION,
                BackendCapability.PREFIX_LOOKUP,
                BackendCapability.HIT_ATTRIBUTION,
                BackendCapability.GENERATION_SAFETY,
            }
        ),
    )


class BackendConformanceTest(unittest.TestCase):
    def test_mlx_adapter_passes_backend_contract_v02_conformance(self) -> None:
        report = run_backend_conformance(MLXConformanceDriver)
        self.assertTrue(report.passed, report.to_dict())
        self.assertEqual(report.descriptor.integration_level, "generation-safe-managed")
        self.assertEqual(report.passed_count, 7)
        self.assertEqual(report.skipped_count, 0)
        self.assertEqual(report.failed_count, 0)

    def test_unsupported_capabilities_are_explicit_skips(self) -> None:
        report = run_backend_conformance(PartialConformanceDriver)
        self.assertTrue(report.passed)
        self.assertEqual(report.passed_count, 1)
        self.assertEqual(report.skipped_count, 6)
        self.assertIs(report.results[0].status, ConformanceStatus.PASS)
        self.assertTrue(
            all(
                result.status is ConformanceStatus.SKIP
                for result in report.results[1:]
            )
        )

    def test_lookup_and_generation_can_conform_without_admission_ownership(self) -> None:
        report = run_backend_conformance(ObserveGenerationConformanceDriver)
        self.assertTrue(report.passed, report.to_dict())
        self.assertEqual(report.descriptor.integration_level, "observe")
        self.assertEqual(report.passed_count, 4)
        self.assertEqual(report.skipped_count, 3)
        self.assertEqual(report.failed_count, 0)
        self.assertEqual(
            {result.name for result in report.results if result.status is ConformanceStatus.PASS},
            {
                "namespace_identity",
                "namespace_isolation_and_same_domain_reuse",
                "actual_prefix_hit_attribution",
                "generation_safe_exact_reuse",
            },
        )


if __name__ == "__main__":
    unittest.main()
