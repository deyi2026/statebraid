import unittest

from statebraid.adapters.llama_cpp import (
    LLAMA_CPP_BACKEND_DESCRIPTOR,
    normalize_llama_cpp_reuse,
)
from statebraid.backend import (
    ConformanceStatus,
    UnsupportedBackendCapability,
    run_backend_conformance,
)


class LlamaCppPublicConformanceDriver:
    """Test fixture for the public timing semantics of one llama-server slot."""

    descriptor = LLAMA_CPP_BACKEND_DESCRIPTOR

    def __init__(self, max_sequences: int, max_bytes: int):
        del max_sequences, max_bytes
        self.resident = ()
        self.hits = {}

    def cache_key(self, trust_domain, tokens):
        return (trust_domain, tuple(tokens))

    def payload(self, nbytes: int) -> object:
        return {"opaque_bytes": nbytes}

    def seed(self, trust_domain, tokens, payload, *, role, nbytes) -> None:
        del trust_domain, payload, role, nbytes
        self.resident = tuple(tokens)

    @staticmethod
    def _lcp(left, right):
        n = 0
        for lval, rval in zip(left, right):
            if lval != rval:
                break
            n += 1
        return n

    def lookup(self, trust_domain, tokens):
        del trust_domain
        prompt = tuple(tokens)
        cache_n = self._lcp(self.resident, prompt)
        observation = normalize_llama_cpp_reuse(
            backend_identity="fake-llama-server",
            id_slot=0,
            prompt_tokens=prompt,
            response={
                "timings": {
                    "cache_n": cache_n,
                    "prompt_n": len(prompt) - cache_n,
                }
            },
        )
        if observation.matched_key is not None:
            key = observation.matched_key.tokens
            self.hits[key] = self.hits.get(key, 0) + 1
        # An execution-coupled observation leaves the new prompt in the slot.
        self.resident = prompt
        return observation

    def entry_hits(self, trust_domain, tokens):
        del trust_domain
        return self.hits.get(tuple(tokens))

    def generation_safe_exact(self, trust_domain, tokens):
        del trust_domain
        prompt = tuple(tokens)
        if self.resident != prompt:
            raise RuntimeError("generation-safe exact fixture was not seeded exactly")
        cache_n = max(0, len(prompt) - 1)
        return normalize_llama_cpp_reuse(
            backend_identity="fake-llama-server",
            id_slot=0,
            prompt_tokens=prompt,
            response={
                "timings": {
                    "cache_n": cache_n,
                    "prompt_n": len(prompt) - cache_n,
                }
            },
        )

    def admit(self, *args, **kwargs):
        del args, kwargs
        raise UnsupportedBackendCapability("llama.cpp public adapter does not own admission")

    def contains(self, *args, **kwargs):
        del args, kwargs
        raise UnsupportedBackendCapability("llama.cpp public adapter does not own residency")

    def resident_stats(self):
        raise UnsupportedBackendCapability("llama.cpp public adapter does not own residency")

    def fail_next_insert(self):
        raise UnsupportedBackendCapability("llama.cpp public adapter has no transaction API")


class LlamaCppConformanceContractTest(unittest.TestCase):
    def test_public_llama_cpp_capabilities_pass_without_ownership_inflation(self):
        report = run_backend_conformance(LlamaCppPublicConformanceDriver)
        self.assertTrue(report.passed, report.to_dict())
        self.assertEqual(report.descriptor.integration_level, "partial")
        self.assertEqual(report.passed_count, 2)
        self.assertEqual(report.skipped_count, 5)
        self.assertEqual(report.failed_count, 0)
        passed = {
            item.name
            for item in report.results
            if item.status is ConformanceStatus.PASS
        }
        self.assertEqual(
            passed,
            {"actual_prefix_hit_attribution", "generation_safe_exact_reuse"},
        )
        skipped = {
            item.name
            for item in report.results
            if item.status is ConformanceStatus.SKIP
        }
        self.assertIn("namespace_identity", skipped)
        self.assertIn("transaction_rollback", skipped)

    def test_generation_safety_allows_safe_full_recompute(self):
        class FullRecomputeDriver(LlamaCppPublicConformanceDriver):
            def generation_safe_exact(self, trust_domain, tokens):
                del trust_domain
                prompt = tuple(tokens)
                return normalize_llama_cpp_reuse(
                    backend_identity="fake-llama-server",
                    id_slot=0,
                    prompt_tokens=prompt,
                    response={
                        "timings": {"cache_n": 0, "prompt_n": len(prompt)}
                    },
                )

        report = run_backend_conformance(FullRecomputeDriver)
        result = next(
            item for item in report.results if item.name == "generation_safe_exact_reuse"
        )
        self.assertIs(result.status, ConformanceStatus.PASS)


if __name__ == "__main__":
    unittest.main()
