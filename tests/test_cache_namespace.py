import unittest

from statebraid.cache import (
    DEFAULT_TRUST_DOMAIN,
    MAX_TRUST_DOMAIN_BYTES,
    CacheNamespace,
    make_cache_namespace,
    validate_trust_domain,
)


class CacheNamespaceTest(unittest.TestCase):
    def test_default_domain_is_stable_and_backend_scoped(self) -> None:
        left = make_cache_namespace(("model-a", None, None))
        same = make_cache_namespace(("model-a", None, None))
        other_backend = make_cache_namespace(("model-b", None, None))

        self.assertEqual(left, same)
        self.assertNotEqual(left, other_backend)
        self.assertEqual(left.trust_domain, DEFAULT_TRUST_DOMAIN)

    def test_same_backend_different_domains_are_distinct(self) -> None:
        backend = ("model-a", None, None)
        tenant_a = make_cache_namespace(backend, "tenant-a")
        tenant_b = make_cache_namespace(backend, "tenant-b")

        self.assertNotEqual(tenant_a, tenant_b)
        self.assertIsInstance(tenant_a, CacheNamespace)

    def test_domain_validation_is_exact_and_non_semantic(self) -> None:
        for value in ("tenant-1", "org.example", "scope_v2", "a:b"):
            with self.subTest(value=value):
                self.assertEqual(validate_trust_domain(value), value)

    def test_hostile_or_ambiguous_domains_are_rejected(self) -> None:
        invalid = (
            "",
            " leading",
            "trailing ",
            "a/b",
            "a\\b",
            "line\nbreak",
            "tenant-☃",
            "x" * (MAX_TRUST_DOMAIN_BYTES + 1),
        )
        for value in invalid:
            with self.subTest(value=value[:20]):
                with self.assertRaises(ValueError):
                    validate_trust_domain(value)

        with self.assertRaises(TypeError):
            validate_trust_domain(123)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main(verbosity=2)
