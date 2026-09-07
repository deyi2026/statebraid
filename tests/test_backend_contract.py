import unittest

from statebraid.backend import (
    BACKEND_CONTRACT_VERSION,
    BackendCapability,
    BackendDescriptor,
    LookupObservation,
    UnsupportedBackendCapability,
)


class BackendContractTest(unittest.TestCase):
    def test_contract_version_and_partial_capability_levels(self) -> None:
        identity = BackendDescriptor(
            name="identity-only",
            adapter="tests.identity",
            capabilities=frozenset({BackendCapability.NAMESPACE_ISOLATION}),
        )
        self.assertEqual(BACKEND_CONTRACT_VERSION, "0.2")
        self.assertEqual(identity.integration_level, "identity-only")
        self.assertTrue(identity.supports(BackendCapability.NAMESPACE_ISOLATION))
        self.assertFalse(identity.supports(BackendCapability.PREFIX_LOOKUP))
        with self.assertRaises(UnsupportedBackendCapability):
            identity.require(BackendCapability.PREFIX_LOOKUP)

    def test_capability_dependencies_fail_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "prefix_lookup"):
            BackendDescriptor(
                name="bad-hit",
                adapter="tests.bad",
                capabilities=frozenset({BackendCapability.HIT_ATTRIBUTION}),
            )
        with self.assertRaisesRegex(ValueError, "transactional_mutation"):
            BackendDescriptor(
                name="bad-rollback",
                adapter="tests.bad",
                capabilities=frozenset({BackendCapability.ROLLBACK}),
            )

    def test_lookup_observation_normalizes_exact_prefix_identity(self) -> None:
        payload = object()
        observation = LookupObservation.from_backend_result(
            "namespace", [1, 2, 3, 4], payload, [3, 4]
        )
        self.assertTrue(observation.hit)
        self.assertFalse(observation.exact)
        self.assertEqual(observation.matched_tokens, 2)
        self.assertIsNotNone(observation.matched_key)
        assert observation.matched_key is not None
        self.assertEqual(observation.matched_key.tokens, (1, 2))
        self.assertEqual(observation.remaining, (3, 4))

    def test_lookup_observation_rejects_inconsistent_backend_evidence(self) -> None:
        with self.assertRaisesRegex(ValueError, "exact prompt suffix"):
            LookupObservation.from_backend_result("n", [1, 2, 3], object(), [9])
        with self.assertRaisesRegex(ValueError, "without a payload"):
            LookupObservation.from_backend_result("n", [1, 2, 3], None, [3])
        with self.assertRaisesRegex(ValueError, "without a matched prefix"):
            LookupObservation.from_backend_result("n", [1, 2, 3], object(), [1, 2, 3])


if __name__ == "__main__":
    unittest.main()
